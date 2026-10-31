from collections import defaultdict
from pathlib import Path, PurePosixPath
from tree_sitter import Parser
from ingestion.chunker import JS_TS_PARSERS, SYNTHETIC_HEADER_PREFIXES, CodeChunk, py_parser
from ingestion.loader import LoadedFile

CODE_EXTENSIONS = (".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".mts", ".cts")
BARREL_FILES = ("__init__.py", "index.ts", "index.tsx", "index.js", "index.jsx")
IGNORED_CALL_NAMES = {
    "__init__",
    "__new__",
    "__str__",
    "__repr__",
    "constructor",
    "super",
    "print",
    "len",
    "str",
    "int",
    "float",
    "bool",
    "list",
    "dict",
    "set",
    "tuple",
    "range",
    "enumerate",
    "zip",
    "min",
    "max",
    "sum",
    "sorted",
    "any",
    "all",
    "isinstance",
    "getattr",
    "setattr",
    "hasattr",
    "next",
    "iter",
    "open",
}


def _node_text(node, code_bytes: bytes) -> str:
    return code_bytes[node.start_byte : node.end_byte].decode("utf8", errors="ignore")


def _strip_quotes(raw: str) -> str:
    return raw.strip().strip("\"'`")


class DependencyAnalyzer:
    """Extracts file imports, class inheritance, and function/method call graphs using Tree-sitter ASTs."""

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
            # Try from repo root and from each ancestor package directory of importing_file (e.g. backend/)
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

            # Exact match (when extension is already in specifier)
            if base_str in all_files and base_str != importing_file and base_str not in seen:
                seen.add(base_str)
                resolved.append(base_str)
                continue

            # Probe known code extensions
            for ext in CODE_EXTENSIONS:
                with_ext = f"{base_str}{ext}"
                if with_ext in all_files and with_ext != importing_file and with_ext not in seen:
                    seen.add(with_ext)
                    resolved.append(with_ext)

            # Probe barrel files (index.ts, __init__.py, etc.)
            for barrel in BARREL_FILES:
                barrel_path = f"{base_str}/{barrel}"
                if barrel_path in all_files and barrel_path != importing_file and barrel_path not in seen:
                    seen.add(barrel_path)
                    resolved.append(barrel_path)

        return resolved

    def _extract_python_file_relations(
        self, code_bytes: bytes
    ) -> tuple[list[tuple[str, list[str]]], dict[str, list[str]]]:
        """Returns ([(module_specifier, [imported_symbols])], {class_name: [base_classes]})."""
        tree = py_parser.parse(code_bytes)
        imports: list[tuple[str, list[str]]] = []
        inheritance: dict[str, list[str]] = defaultdict(list)

        def visit(node) -> None:
            if node.type == "import_statement":
                for child in node.children:
                    if child.type == "dotted_name":
                        imports.append((_node_text(child, code_bytes), []))
                    elif child.type == "aliased_import":
                        dotted = next((c for c in child.children if c.type == "dotted_name"), None)
                        if dotted:
                            imports.append((_node_text(dotted, code_bytes), []))
                return

            if node.type == "import_from_statement":
                module_spec = ""
                imported_syms: list[str] = []
                seen_import_kw = False
                for child in node.children:
                    if child.type == "import":
                        seen_import_kw = True
                    elif not seen_import_kw and child.type in {"dotted_name", "relative_import"}:
                        module_spec = _node_text(child, code_bytes)
                    elif seen_import_kw:
                        if child.type == "dotted_name":
                            imported_syms.append(_node_text(child, code_bytes))
                        elif child.type == "aliased_import":
                            orig = next((c for c in child.children if c.type == "dotted_name"), None)
                            if orig:
                                imported_syms.append(_node_text(orig, code_bytes))
                imports.append((module_spec, imported_syms))
                return

            if node.type == "class_definition":
                cls_id = next((c for c in node.children if c.type == "identifier"), None)
                arg_list = next((c for c in node.children if c.type == "argument_list"), None)
                if cls_id and arg_list:
                    cls_name = _node_text(cls_id, code_bytes)
                    for arg in arg_list.children:
                        if arg.type == "identifier":
                            inheritance[cls_name].append(_node_text(arg, code_bytes))
                        elif arg.type == "attribute":
                            ident_children = [c for c in arg.children if c.type == "identifier"]
                            if ident_children:
                                inheritance[cls_name].append(_node_text(ident_children[-1], code_bytes))
                        elif arg.type == "subscript":
                            base_id = next((c for c in arg.children if c.type == "identifier"), None)
                            if base_id:
                                inheritance[cls_name].append(_node_text(base_id, code_bytes))

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return imports, inheritance

    def _extract_js_ts_file_relations(
        self, code_bytes: bytes, parser: Parser
    ) -> tuple[list[tuple[str, list[str]]], dict[str, list[str]]]:
        """Returns ([(module_specifier, [imported_symbols])], {class_name: [base_classes]})."""
        tree = parser.parse(code_bytes)
        imports: list[tuple[str, list[str]]] = []
        inheritance: dict[str, list[str]] = defaultdict(list)

        def collect_identifiers(n, out: list[str]) -> None:
            if n.type in {"identifier", "type_identifier"}:
                out.append(_node_text(n, code_bytes))
                return
            for ch in n.children:
                collect_identifiers(ch, out)

        def visit(node) -> None:
            if node.type in {"import_statement", "export_statement"}:
                str_node = next((c for c in node.children if c.type == "string"), None)
                if str_node:
                    spec = _strip_quotes(_node_text(str_node, code_bytes))
                    syms: list[str] = []
                    for c in node.children:
                        if c.type in {"import_clause", "export_clause"}:
                            collect_identifiers(c, syms)
                    imports.append((spec, syms))
                return

            if node.type == "call_expression":
                fn = node.children[0] if node.children else None
                args = next((c for c in node.children if c.type == "arguments"), None)
                if fn and args and _node_text(fn, code_bytes) in {"require", "import"}:
                    str_node = next((c for c in args.children if c.type == "string"), None)
                    if str_node:
                        imports.append((_strip_quotes(_node_text(str_node, code_bytes)), []))

            if node.type in {"class_declaration", "abstract_class_declaration"}:
                cls_id = next((c for c in node.children if c.type in {"identifier", "type_identifier"}), None)
                heritage = next((c for c in node.children if c.type == "class_heritage"), None)
                if cls_id and heritage:
                    cls_name = _node_text(cls_id, code_bytes)
                    bases: list[str] = []
                    collect_identifiers(heritage, bases)
                    inheritance[cls_name].extend(b for b in bases if b != cls_name)

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return imports, inheritance

    def _extract_chunk_calls(self, chunk: CodeChunk) -> list[tuple[str, str]]:
        """Extracts (receiver, callee_name) pairs from a chunk's AST."""
        ext = Path(chunk.file_path).suffix.lower()
        parser = py_parser if ext == ".py" else JS_TS_PARSERS.get(ext)
        if parser is None:
            return []

        # Strip synthetic `# File:` / `# Class:` / dependency header comments before parsing
        raw_lines = [
            line
            for line in chunk.content.splitlines()
            if not line.startswith(SYNTHETIC_HEADER_PREFIXES)
        ]
        code_bytes = "\n".join(raw_lines).encode("utf8", errors="ignore")
        tree = parser.parse(code_bytes)
        calls: list[tuple[str, str]] = []

        def visit(node) -> None:
            # Python call: `func(...)` or `obj.method(...)`
            if node.type == "call":
                func_node = node.children[0] if node.children else None
                if func_node is not None:
                    if func_node.type == "identifier":
                        calls.append(("", _node_text(func_node, code_bytes)))
                    elif func_node.type == "attribute":
                        idents = [c for c in func_node.children if c.type == "identifier"]
                        if len(idents) >= 2:
                            calls.append((_node_text(idents[0], code_bytes), _node_text(idents[-1], code_bytes)))
                        elif len(idents) == 1:
                            calls.append(("", _node_text(idents[0], code_bytes)))

            # JS/TS call_expression or `new ClassName(...)`
            elif node.type in {"call_expression", "new_expression"}:
                target = next(
                    (
                        c
                        for c in node.children
                        if c.type in {"identifier", "type_identifier", "member_expression"}
                    ),
                    None,
                )
                if target is not None:
                    if target.type in {"identifier", "type_identifier"}:
                        calls.append(("", _node_text(target, code_bytes)))
                    elif target.type == "member_expression":
                        idents = [
                            c
                            for c in target.children
                            if c.type in {"identifier", "property_identifier", "this"}
                        ]
                        if len(idents) >= 2:
                            calls.append((_node_text(idents[0], code_bytes), _node_text(idents[-1], code_bytes)))
                        elif len(idents) == 1:
                            calls.append(("", _node_text(idents[0], code_bytes)))

            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return calls

    @staticmethod
    def _inject_dependency_headers(chunk: CodeChunk) -> None:
        """Inserts compact `# Imports:`, `# Inherits from:`, and `# Calls:` metadata lines into chunk.content."""
        lines = chunk.content.splitlines()
        header_end = 0
        while header_end < len(lines) and (
            lines[header_end].startswith("# File:")
            or lines[header_end].startswith("# Class:")
            or lines[header_end].startswith("# Function:")
        ):
            header_end += 1

        # Remove any previous dependency header lines so re-running analyze() is idempotent
        body_start = header_end
        while body_start < len(lines) and (
            lines[body_start].startswith("# Imports:")
            or lines[body_start].startswith("# Imported by:")
            or lines[body_start].startswith("# Inherits from:")
            or lines[body_start].startswith("# Calls:")
            or lines[body_start].startswith("# Called by:")
        ):
            body_start += 1

        dep_lines: list[str] = []
        if chunk.node_type in {"module_preamble", "class", "class_header"}:
            file_parts: list[str] = []
            if chunk.imports:
                file_parts.append(f"# Imports: {', '.join(chunk.imports[:6])}")
            if chunk.imported_by:
                file_parts.append(f"# Imported by: {', '.join(chunk.imported_by[:6])}")
            if file_parts:
                dep_lines.append(" | ".join(file_parts))

        if chunk.inherits_from:
            dep_lines.append(f"# Inherits from: {', '.join(chunk.inherits_from)}")

        call_parts: list[str] = []
        if chunk.calls:
            call_parts.append(f"# Calls: {', '.join(chunk.calls[:8])}")
        if chunk.called_by:
            call_parts.append(f"# Called by: {', '.join(chunk.called_by[:8])}")
        if call_parts:
            dep_lines.append(" | ".join(call_parts))

        if dep_lines:
            chunk.content = "\n".join(lines[:header_end] + dep_lines + lines[body_start:])

    def _extract_atomic_class_methods(self, chunk: CodeChunk) -> list[str]:
        """Extracts method names declared inside an atomic `class` chunk."""
        ext = Path(chunk.file_path).suffix.lower()
        parser = py_parser if ext == ".py" else JS_TS_PARSERS.get(ext)
        if parser is None:
            return []

        raw_lines = [
            line for line in chunk.content.splitlines() if not line.startswith(SYNTHETIC_HEADER_PREFIXES)
        ]
        code_bytes = "\n".join(raw_lines).encode("utf8", errors="ignore")
        tree = parser.parse(code_bytes)
        methods: list[str] = []

        def visit(node) -> None:
            if node.type in {"function_definition", "method_definition", "abstract_method_signature"}:
                name_node = next(
                    (c for c in node.children if c.type in {"identifier", "property_identifier"}),
                    None,
                )
                if name_node is not None:
                    name = _node_text(name_node, code_bytes)
                    if name and name not in IGNORED_CALL_NAMES and name not in methods:
                        methods.append(name)
            for child in node.children:
                visit(child)

        visit(tree.root_node)
        return methods

    def analyze(self, chunks: list[CodeChunk], files: list[LoadedFile] | None = None) -> list[CodeChunk]:
        """Populates file imports, class inheritance, and function call graphs across all chunks."""
        if not chunks:
            return chunks

        # 1. Gather full source per file (from LoadedFile if provided, else reconstructed from chunks)
        file_sources: dict[str, bytes] = {}
        if files:
            for f in files:
                file_sources[f.file_path] = f.content.encode("utf8", errors="ignore")
        else:
            by_file_lines: dict[str, list[str]] = defaultdict(list)
            for c in chunks:
                if c.node_type == "file_summary":
                    continue
                for line in c.content.splitlines():
                    if not line.startswith(SYNTHETIC_HEADER_PREFIXES):
                        by_file_lines[c.file_path].append(line)
            for fp, lns in by_file_lines.items():
                file_sources[fp] = "\n".join(lns).encode("utf8", errors="ignore")

        all_files = {c.file_path for c in chunks} | set(file_sources.keys())

        # 2. Extract file-level imports and class inheritance per file
        file_imports: dict[str, list[str]] = defaultdict(list)
        file_imported_by: dict[str, list[str]] = defaultdict(list)
        class_bases: dict[tuple[str, str], list[str]] = {}

        for fp, code_bytes in sorted(file_sources.items()):
            ext = Path(fp).suffix.lower()
            if ext == ".py":
                raw_imports, inherits = self._extract_python_file_relations(code_bytes)
            elif ext in JS_TS_PARSERS:
                raw_imports, inherits = self._extract_js_ts_file_relations(code_bytes, JS_TS_PARSERS[ext])
            else:
                continue

            resolved_targets: list[str] = []
            for spec, syms in raw_imports:
                for target_fp in self._resolve_import_specifier(fp, spec, syms, all_files):
                    if target_fp not in resolved_targets:
                        resolved_targets.append(target_fp)

            file_imports[fp] = resolved_targets
            for target_fp in resolved_targets:
                if fp not in file_imported_by[target_fp]:
                    file_imported_by[target_fp].append(fp)

            for cls_name, bases in inherits.items():
                class_bases[(fp, cls_name)] = list(dict.fromkeys(bases))

        # 3. Build symbol index across all chunks for call-graph resolution
        #    symbol_name -> list of chunks defining that symbol
        defs_by_symbol: dict[str, list[CodeChunk]] = defaultdict(list)
        for c in chunks:
            if c.symbol_name and c.node_type in {"function", "method", "class", "class_header"}:
                defs_by_symbol[c.symbol_name].append(c)
            if c.node_type == "class":
                for method_name in self._extract_atomic_class_methods(c):
                    if c not in defs_by_symbol[method_name]:
                        defs_by_symbol[method_name].append(c)

        # Track reverse call edges: id(target_chunk) -> list of caller symbol names
        called_by_map: dict[int, list[str]] = defaultdict(list)

        # 4. Resolve calls and inheritance for each chunk
        for c in chunks:
            c.imports = list(file_imports.get(c.file_path, []))
            c.imported_by = list(file_imported_by.get(c.file_path, []))

            # Attach class inheritance if chunk is a class, class_header, or method of that class
            cls_key = (c.file_path, c.parent_class or c.symbol_name)
            if cls_key in class_bases:
                c.inherits_from = list(class_bases[cls_key])

            if c.node_type not in {"function", "method", "class", "module_preamble"}:
                continue

            raw_calls = self._extract_chunk_calls(c)
            imported_set = set(c.imports)
            resolved_callees: list[str] = []

            for receiver, callee in raw_calls:
                if not callee or callee in IGNORED_CALL_NAMES or callee == c.symbol_name:
                    continue
                target_defs = defs_by_symbol.get(callee)
                if not target_defs:
                    continue

                matched_targets: list[CodeChunk] = []

                # Priority 1: `self.method()` or `this.method()` -> same class or base class
                if receiver in {"self", "cls", "this"} and c.parent_class:
                    allowed_classes = {c.parent_class} | set(c.inherits_from)
                    matched_targets = [t for t in target_defs if t.parent_class in allowed_classes]

                # Priority 2: Defined in the same file
                if not matched_targets:
                    matched_targets = [t for t in target_defs if t.file_path == c.file_path]

                # Priority 3: Defined in a file imported by this file
                if not matched_targets:
                    matched_targets = [t for t in target_defs if t.file_path in imported_set]

                # Priority 4: Repo-wide fallback ONLY if the symbol is defined in a single file across the repo
                if not matched_targets:
                    unique_files = {t.file_path for t in target_defs}
                    if len(unique_files) == 1:
                        matched_targets = target_defs

                if matched_targets:
                    if callee not in resolved_callees:
                        resolved_callees.append(callee)
                    caller_label = (
                        f"{c.parent_class}.{c.symbol_name}"
                        if c.parent_class and c.symbol_name and c.parent_class != c.symbol_name
                        else (c.symbol_name or Path(c.file_path).stem)
                    )
                    for target in matched_targets:
                        if caller_label and caller_label not in called_by_map[id(target)]:
                            called_by_map[id(target)].append(caller_label)

            c.calls = resolved_callees

        # 5. Apply reverse `called_by` edges and propagate between class_header and class methods
        for c in chunks:
            callers = list(called_by_map.get(id(c), []))
            # If a class is instantiated by callers, share that with its class_header
            if c.node_type in {"class", "class_header", "function", "method"}:
                c.called_by = callers
            self._inject_dependency_headers(c)

        return chunks
