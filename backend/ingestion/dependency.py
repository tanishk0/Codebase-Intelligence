from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from tree_sitter import Parser
from ingestion.chunker import JS_TS_PARSERS, CodeChunk, get_node_text, py_parser
from ingestion.loader import LoadedFile

# Bump when import/call/inheritance extraction changes, so stored edge metadata is rebuilt.
DEPENDENCY_VERSION = 1

CODE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
BARREL_FILES = ("__init__.py", "index.ts", "index.tsx", "index.js", "index.jsx")
IGNORED_CALL_NAMES = {
    # Lifecycle & constructors
    "__init__", "__new__", "__str__", "__repr__", "constructor", "super",
    # Python built-in functions
    "print", "len", "str", "int", "float", "bool", "list", "dict", "set",
    "tuple", "range", "enumerate", "zip", "min", "max", "sum", "sorted",
    "any", "all", "isinstance", "getattr", "setattr", "hasattr", "next",
    "iter", "open",
    # Common built-in container/string methods (prevents false edges on dict.get, list.append, etc.)
    "get", "append", "extend", "update", "pop", "split", "strip", "lstrip",
    "rstrip", "replace", "join", "items", "keys", "values", "lower", "upper",
    "startswith", "endswith", "encode", "decode", "format", "splitlines",
    "add", "remove", "clear", "copy", "count", "sort", "reverse",
    "push", "slice", "splice", "map", "filter", "reduce", "forEach", "includes", "trim",
}


def _strip_quotes(raw: str) -> str:
    return raw.strip().strip("\"'`")


def _collect_identifiers(node, code_bytes: bytes, out: list[str], *, allow_this: bool = False) -> None:
    """Recursively collects identifier texts inside an AST subtree in source order."""
    types = {"identifier", "type_identifier", "property_identifier"}
    if allow_this:
        types.add("this")
    if node.type in types:
        out.append(get_node_text(node, code_bytes))
        return
    for child in node.children:
        _collect_identifiers(child, code_bytes, out, allow_this=allow_this)


@dataclass
class _FileASTSummary:
    raw_imports: list[tuple[str, list[str]]] = field(default_factory=list)
    # Maps the local name used at a call site to the symbol's exported name.
    # For example: ``from crypto import verify as verify_token``.
    import_aliases: dict[str, str] = field(default_factory=dict)
    inheritance: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    class_methods: dict[str, list[str]] = field(default_factory=lambda: defaultdict(list))
    calls: list[tuple[int, str, str]] = field(default_factory=list)  # (line_number, receiver, callee)


class DependencyAnalyzer:
    """Single-pass Tree-sitter analyzer for file imports, class inheritance, and function/method call graphs."""

    def _resolve_import_specifier(
        self,
        importing_file: str,
        specifier: str,
        imported_symbols: list[str],
        all_files: set[str],
    ) -> list[str]:
        """Resolves a raw Python or JS/TS import specifier to actual repository file paths."""
        if not specifier:
            return []

        importer_dir = PurePosixPath(importing_file).parent
        candidate_bases: list[PurePosixPath] = []

        # 1. JS/TS relative paths: ./foo, ../bar
        if specifier.startswith("./") or specifier.startswith("../"):
            rel_parts = list(importer_dir.parts)
            for token in PurePosixPath(specifier).parts:
                if token == ".":
                    continue
                if token == "..":
                    if rel_parts:
                        rel_parts.pop()
                else:
                    rel_parts.append(token)
            if rel_parts:
                candidate_bases.append(PurePosixPath(*rel_parts))

        # 2. Common JS/TS path aliases: @/components/Button, ~/utils/api
        elif specifier.startswith("@/") or specifier.startswith("~/"):
            stripped = specifier[2:]
            for prefix in ("", "src", "app", "frontend", "frontend/src", "backend"):
                candidate_bases.append(PurePosixPath(prefix) / stripped if prefix else PurePosixPath(stripped))

        # 3. Python relative imports: .loader, ..config
        elif specifier.startswith("."):
            dots = len(specifier) - len(specifier.lstrip("."))
            remainder = specifier.lstrip(".").replace(".", "/")
            rel_parts = list(importer_dir.parts)
            for _ in range(max(0, dots - 1)):
                if rel_parts:
                    rel_parts.pop()
            base_path = PurePosixPath(*rel_parts) if rel_parts else PurePosixPath(".")
            if remainder:
                candidate_bases.append(base_path / remainder)
            for sym in imported_symbols:
                candidate_bases.append((base_path / remainder / sym) if remainder else (base_path / sym))

        # 4. Standard module path (Python dotted `ingestion.chunker` or JS bare/root path)
        else:
            slash_path = specifier.replace(".", "/") if "/" not in specifier else specifier
            ancestors: list[PurePosixPath] = [PurePosixPath(".")]
            cur = importer_dir
            while str(cur) not in {"", "."}:
                ancestors.append(cur)
                cur = cur.parent

            for anc in ancestors:
                base = PurePosixPath(slash_path) if str(anc) == "." else (anc / slash_path)
                candidate_bases.append(base)
                for sym in imported_symbols:
                    candidate_bases.append(base / sym)

        resolved: list[str] = []
        seen: set[str] = set()

        for base in candidate_bases:
            base_str = base.as_posix().lstrip("./")
            if not base_str:
                continue

            candidates = [base_str]
            candidates.extend(f"{base_str}{ext}" for ext in CODE_EXTENSIONS)
            candidates.extend(f"{base_str}/{barrel}" for barrel in BARREL_FILES)

            for cand in candidates:
                if cand in all_files and cand != importing_file and cand not in seen:
                    seen.add(cand)
                    resolved.append(cand)

        return resolved

    def _parse_file_ast(self, code_bytes: bytes, parser: Parser, is_python: bool) -> _FileASTSummary:
        """Single-pass AST walk extracting imports, inheritance, class methods, and line-tagged calls."""
        tree = parser.parse(code_bytes)
        summary = _FileASTSummary()

        def visit(node, current_class: str = "") -> None:
            ntype = node.type

            # --- 1. Imports ---
            if is_python and ntype == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        summary.raw_imports.append((get_node_text(child, code_bytes), []))
                    elif child.type == "aliased_import":
                        dotted = next((c for c in child.children if c.type == "dotted_name"), None)
                        if dotted:
                            summary.raw_imports.append((get_node_text(dotted, code_bytes), []))
                return

            if is_python and ntype == "import_from_statement":
                module_spec, imported_syms, seen_import_kw = "", [], False
                for child in node.children:
                    if child.type == "import":
                        seen_import_kw = True
                    elif not seen_import_kw and child.type in {"dotted_name", "relative_import"}:
                        module_spec = get_node_text(child, code_bytes)
                    elif seen_import_kw:
                        if child.type == "dotted_name":
                            imported_syms.append(get_node_text(child, code_bytes))
                        elif child.type == "aliased_import":
                            orig = next((c for c in child.children if c.type == "dotted_name"), None)
                            if orig:
                                original_name = get_node_text(orig, code_bytes)
                                imported_syms.append(original_name)
                                local_name = next(
                                    (
                                        get_node_text(c, code_bytes)
                                        for c in child.children
                                        if c.type == "identifier"
                                    ),
                                    "",
                                )
                                if local_name:
                                    summary.import_aliases[local_name] = original_name
                summary.raw_imports.append((module_spec, imported_syms))
                return

            if not is_python and ntype in {"import_statement", "export_statement"}:
                str_node = next((c for c in node.children if c.type == "string"), None)
                if str_node:
                    spec = _strip_quotes(get_node_text(str_node, code_bytes))
                    syms: list[str] = []
                    for c in node.children:
                        if c.type in {"import_clause", "export_clause"}:
                            _collect_identifiers(c, code_bytes, syms)
                    summary.raw_imports.append((spec, syms))
                    return
                if ntype == "import_statement":
                    return

            # --- 2. Classes & Inheritance ---
            if ntype in {"class_definition", "class_declaration", "abstract_class_declaration"}:
                cls_id = next((c for c in node.children if c.type in {"identifier", "type_identifier"}), None)
                cls_name = get_node_text(cls_id, code_bytes) if cls_id else current_class

                if is_python:
                    arg_list = next((c for c in node.children if c.type == "argument_list"), None)
                    if cls_name and arg_list:
                        for arg in arg_list.children:
                            if arg.type in {"identifier", "attribute", "subscript"}:
                                tokens: list[str] = []
                                _collect_identifiers(arg, code_bytes, tokens)
                                if tokens:
                                    summary.inheritance[cls_name].append(tokens[0] if arg.type == "subscript" else tokens[-1])
                else:
                    heritage = next((c for c in node.children if c.type == "class_heritage"), None)
                    if cls_name and heritage:
                        bases: list[str] = []
                        _collect_identifiers(heritage, code_bytes, bases)
                        summary.inheritance[cls_name].extend(b for b in bases if b != cls_name)

                for child in node.children:
                    visit(child, current_class=cls_name)
                return

            # --- 3. Class method declarations (for atomic small classes) ---
            if current_class and ntype in {"function_definition", "method_definition", "abstract_method_signature"}:
                name_node = next((c for c in node.children if c.type in {"identifier", "property_identifier"}), None)
                if name_node:
                    m_name = get_node_text(name_node, code_bytes)
                    if m_name and m_name not in IGNORED_CALL_NAMES and m_name not in summary.class_methods[current_class]:
                        summary.class_methods[current_class].append(m_name)

            # --- 4. Call sites (handles chained `self.store.method()` accurately) ---
            if ntype in {"call", "call_expression", "new_expression"}:
                target = next(
                    (
                        c
                        for c in node.children
                        if c.type in {"identifier", "type_identifier", "attribute", "member_expression"}
                    ),
                    None,
                )
                if target is not None:
                    line_no = node.start_point[0] + 1
                    tokens: list[str] = []
                    _collect_identifiers(target, code_bytes, tokens, allow_this=True)
                    if len(tokens) == 1:
                        callee = tokens[0]
                        if not is_python and callee in {"require", "import"}:
                            args = next((c for c in node.children if c.type == "arguments"), None)
                            str_node = next((c for c in (args.children if args else []) if c.type == "string"), None)
                            if str_node:
                                summary.raw_imports.append((_strip_quotes(get_node_text(str_node, code_bytes)), []))
                        else:
                            summary.calls.append((line_no, "", callee))
                    elif len(tokens) >= 2:
                        receiver = ".".join(tokens[:-1])
                        summary.calls.append((line_no, receiver, tokens[-1]))

            for child in node.children:
                visit(child, current_class)

        visit(tree.root_node)
        return summary

    @staticmethod
    def _inject_dependency_headers(chunk: CodeChunk) -> None:
        """Inserts compact `# Imports:`, `# Inherits from:`, and `# Calls:` metadata lines into chunk.content."""
        lines = chunk.content.splitlines()
        header_end = 0
        while header_end < len(lines) and lines[header_end].startswith(("# File:", "# Class:", "# Function:")):
            header_end += 1

        body_start = header_end
        while body_start < len(lines) and lines[body_start].startswith(
            ("# Imports:", "# Imported by:", "# Inherits from:", "# Calls:", "# Called by:")
        ):
            body_start += 1

        dep_lines: list[str] = []
        if chunk.node_type in {"module_preamble", "class", "class_header"}:
            file_parts = [
                *( [f"# Imports: {', '.join(chunk.imports[:6])}"] if chunk.imports else [] ),
                *( [f"# Imported by: {', '.join(chunk.imported_by[:6])}"] if chunk.imported_by else [] ),
            ]
            if file_parts:
                dep_lines.append(" | ".join(file_parts))

        if chunk.inherits_from:
            dep_lines.append(f"# Inherits from: {', '.join(chunk.inherits_from)}")

        call_parts = [
            *( [f"# Calls: {', '.join(chunk.calls[:8])}"] if chunk.calls else [] ),
            *( [f"# Called by: {', '.join(chunk.called_by[:8])}"] if chunk.called_by else [] ),
        ]
        if call_parts:
            dep_lines.append(" | ".join(call_parts))

        if dep_lines:
            chunk.content = "\n".join(lines[:header_end] + dep_lines + lines[body_start:])

    @staticmethod
    def _gather_file_sources(chunks: list[CodeChunk], files: list[LoadedFile] | None) -> dict[str, bytes]:
        """Returns UTF-8 bytes per file, reconstructing line-accurate source if `files` is not passed."""
        if files:
            return {f.file_path: f.content.encode("utf8", errors="ignore") for f in files}

        by_file: dict[str, list[CodeChunk]] = defaultdict(list)
        for c in chunks:
            if c.node_type != "file_summary":
                by_file[c.file_path].append(c)

        sources: dict[str, bytes] = {}
        for fp, f_chunks in by_file.items():
            max_line = max((c.end_line for c in f_chunks), default=1)
            buf = [""] * max_line
            for c in f_chunks:
                for offset, line in enumerate(c.code_lines()):
                    idx = c.start_line - 1 + offset
                    if 0 <= idx < max_line:
                        buf[idx] = line
            sources[fp] = "\n".join(buf).encode("utf8", errors="ignore")
        return sources

    def analyze(self, chunks: list[CodeChunk], files: list[LoadedFile] | None = None) -> list[CodeChunk]:
        """Populates file imports, class inheritance, and function call graphs across all chunks."""
        if not chunks:
            return chunks

        file_sources = self._gather_file_sources(chunks, files)
        all_files = {c.file_path for c in chunks} | set(file_sources.keys())

        # 1. Single-pass AST parse per file
        file_imports: dict[str, list[str]] = defaultdict(list)
        file_imported_by: dict[str, list[str]] = defaultdict(list)
        class_bases: dict[tuple[str, str], list[str]] = {}
        ast_by_file: dict[str, _FileASTSummary] = {}

        for fp, code_bytes in sorted(file_sources.items()):
            ext = Path(fp).suffix.lower()
            parser = py_parser if ext == ".py" else JS_TS_PARSERS.get(ext)
            if parser is None:
                continue

            summary = self._parse_file_ast(code_bytes, parser, is_python=(ext == ".py"))
            ast_by_file[fp] = summary

            resolved_targets: list[str] = []
            for spec, syms in summary.raw_imports:
                for target_fp in self._resolve_import_specifier(fp, spec, syms, all_files):
                    if target_fp not in resolved_targets:
                        resolved_targets.append(target_fp)

            file_imports[fp] = resolved_targets
            for target_fp in resolved_targets:
                if fp not in file_imported_by[target_fp]:
                    file_imported_by[target_fp].append(fp)

            for cls_name, bases in summary.inheritance.items():
                class_bases[(fp, cls_name)] = list(dict.fromkeys(bases))

        # 2. Build symbol index across all chunks
        defs_by_symbol: dict[str, list[CodeChunk]] = defaultdict(list)
        for c in chunks:
            if c.symbol_name and c.node_type in {"function", "method", "class", "class_header"}:
                defs_by_symbol[c.symbol_name].append(c)
            if c.node_type == "class" and c.file_path in ast_by_file:
                for method_name in ast_by_file[c.file_path].class_methods.get(c.symbol_name, []):
                    if c not in defs_by_symbol[method_name]:
                        defs_by_symbol[method_name].append(c)

        # 3. Resolve calls and inheritance for each chunk using line ranges from the file AST
        called_by_map: dict[int, list[str]] = defaultdict(list)

        for c in chunks:
            c.imports = list(file_imports.get(c.file_path, []))
            c.imported_by = list(file_imported_by.get(c.file_path, []))

            cls_key = (c.file_path, c.parent_class or c.symbol_name)
            if cls_key in class_bases:
                c.inherits_from = list(class_bases[cls_key])

            if c.node_type not in {"function", "method", "class", "module_preamble"}:
                continue

            file_ast = ast_by_file.get(c.file_path)
            if not file_ast:
                continue

            imported_set = set(c.imports)
            resolved_callees: list[str] = []

            for line_no, receiver, callee in file_ast.calls:
                if not (c.start_line <= line_no <= c.end_line):
                    continue
                if not callee or callee in IGNORED_CALL_NAMES or callee == c.symbol_name:
                    continue
                resolved_name = file_ast.import_aliases.get(callee, callee)
                target_defs = defs_by_symbol.get(resolved_name)
                if not target_defs:
                    continue

                matched_targets: list[CodeChunk] = []

                # Priority 1: Direct `self.method()` or `this.method()` -> same class or base class
                if receiver in {"self", "cls", "this"} and c.parent_class:
                    allowed_classes = {c.parent_class} | set(c.inherits_from)
                    matched_targets = [t for t in target_defs if t.parent_class in allowed_classes]

                # A receiver such as ``client.save()`` cannot be resolved safely without
                # type/binding analysis. Do not invent same-file edges for it.
                if receiver and receiver not in {"self", "cls", "this"}:
                    continue

                # Priority 2: Defined in the same file
                if not matched_targets:
                    matched_targets = [t for t in target_defs if t.file_path == c.file_path]

                # Priority 3: Defined in a file imported by this file
                if not matched_targets:
                    matched_targets = [t for t in target_defs if t.file_path in imported_set]

                # Priority 4: Repo-wide fallback ONLY if uniquely defined in a single file across the repo
                if not matched_targets and len({t.file_path for t in target_defs}) == 1:
                    matched_targets = target_defs

                if matched_targets:
                    if resolved_name not in resolved_callees:
                        resolved_callees.append(resolved_name)
                    caller_label = (
                        f"{c.parent_class}.{c.symbol_name}"
                        if c.parent_class and c.symbol_name and c.parent_class != c.symbol_name
                        else (c.symbol_name or Path(c.file_path).stem)
                    )
                    for target in matched_targets:
                        if caller_label and caller_label not in called_by_map[id(target)]:
                            called_by_map[id(target)].append(caller_label)

            c.calls = resolved_callees

        # 4. Apply reverse `called_by` edges and inject headers
        for c in chunks:
            if c.node_type in {"class", "class_header", "function", "method"}:
                c.called_by = list(called_by_map.get(id(c), []))
            self._inject_dependency_headers(c)

        return chunks
