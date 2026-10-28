from dataclasses import dataclass
import re
from tree_sitter import Language, Parser
import tree_sitter_javascript as tsjs
import tree_sitter_python as tspython
import tree_sitter_typescript as tsts
from ingestion.loader import LoadedFile

py_parser = Parser(Language(tspython.language()))
js_parser = Parser(Language(tsjs.language()))
ts_parser = Parser(Language(tsts.language_typescript()))
tsx_parser = Parser(Language(tsts.language_tsx()))

JS_TS_PARSERS: dict[str, Parser] = {
    ".js": js_parser,
    ".jsx": js_parser,
    ".mjs": js_parser,
    ".cjs": js_parser,
    ".ts": ts_parser,
    ".mts": ts_parser,
    ".cts": ts_parser,
    ".tsx": tsx_parser,
}

JS_FUNCTION_VALUE_TYPES = {"arrow_function", "function_expression", "generator_function"}
JS_CLASS_TYPES = {"class_declaration", "abstract_class_declaration"}
JS_DIRECT_FUNC_TYPES = {"function_declaration", "generator_function_declaration"}
JS_METHOD_TYPES = {"method_definition", "abstract_method_signature"}
JS_FIELD_TYPES = {"field_definition", "public_field_definition"}
JS_VAR_DECL_TYPES = {"lexical_declaration", "variable_declaration"}

_CAMEL_BOUNDARY_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_BOUNDARY_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")


def split_identifier_tokens(text: str) -> str:
    """Expands camelCase, PascalCase, and snake_case identifiers into space-separated words for FTS."""
    expanded: list[str] = []
    seen: set[str] = set()
    for match in _IDENT_RE.finditer(text):
        ident = match.group(0)
        if ident in seen:
            continue
        seen.add(ident)
        spaced = _CAMEL_BOUNDARY_1.sub(r"\1 \2", _CAMEL_BOUNDARY_2.sub(r"\1 \2", ident))
        parts = [p.lower() for p in re.split(r"[_\s]+", spaced) if p]
        if len(parts) > 1:
            expanded.extend(parts)
    return " ".join(expanded)


@dataclass
class CodeChunk:
    file_path: str
    content: str
    start_line: int
    end_line: int
    node_type: str         # "method", "function", "class", "class_header", "module_preamble", "text", "file_summary"
    parent_class: str = "" # e.g., "UserRepository"
    symbol_name: str = ""  # e.g., "get_user", "UserRepository"


def build_search_text(chunk: CodeChunk) -> str:
    """Builds keyword-rich text combining file path, symbols, split identifiers, and content for hybrid FTS."""
    path_words = re.sub(r"[/._\-]+", " ", chunk.file_path)
    split_tokens = split_identifier_tokens(
        f"{chunk.file_path} {chunk.parent_class} {chunk.symbol_name} {chunk.content}"
    )
    parts = [
        chunk.file_path,
        path_words,
        chunk.parent_class,
        chunk.symbol_name,
        split_tokens,
        chunk.content,
    ]
    return " ".join(p for p in parts if p)


class TreeSitterChunker:
    def __init__(
        self,
        max_class_lines: int = 50,
        max_function_lines: int = 120,
        fallback_chunk_lines: int = 60,
        fallback_overlap_lines: int = 10,
    ):
        self.max_class_lines = max_class_lines
        self.max_function_lines = max_function_lines
        self.fallback_chunk_lines = fallback_chunk_lines
        self.fallback_overlap_lines = fallback_overlap_lines

    def _get_node_text(self, node, code_bytes: bytes) -> str:
        return code_bytes[node.start_byte:node.end_byte].decode("utf8", errors="ignore")

    def _unwrap_decorated(self, node):
        """If node is decorated_definition, return (wrapper_node, inner_def_node)."""
        if node.type == "decorated_definition":
            for child in node.children:
                if child.type in {"function_definition", "class_definition"}:
                    return node, child
        return node, node

    def _unwrap_js_export(self, node):
        """If node is export_statement, return (export_node, inner_declaration_node)."""
        if node.type == "export_statement":
            for child in node.children:
                if child.type in (JS_CLASS_TYPES | JS_DIRECT_FUNC_TYPES | JS_VAR_DECL_TYPES):
                    return node, child
        return node, node

    def _get_class_name(self, class_node, code_bytes: bytes) -> str:
        for child in class_node.children:
            if child.type in {"identifier", "type_identifier"}:
                return self._get_node_text(child, code_bytes)
        return "UnknownClass"

    def _get_function_name(self, func_node, code_bytes: bytes) -> str:
        for child in func_node.children:
            if child.type in {"identifier", "property_identifier", "type_identifier"}:
                return self._get_node_text(child, code_bytes)
            if child.type == "variable_declarator":
                for sub in child.children:
                    if sub.type in {"identifier", "property_identifier"}:
                        return self._get_node_text(sub, code_bytes)
        return ""

    def _is_js_function_field(self, field_node) -> bool:
        """True if a class field_definition / public_field_definition assigns a function or arrow function."""
        return any(child.type in JS_FUNCTION_VALUE_TYPES for child in field_node.children)

    def _is_js_function_var_decl(self, decl_node) -> bool:
        """True if a lexical/variable declaration defines a function (e.g., const fn = () => {} or React.memo(() => {}))."""
        for child in decl_node.children:
            if child.type != "variable_declarator":
                continue
            for sub in child.children:
                if sub.type in JS_FUNCTION_VALUE_TYPES:
                    return True
                # Handle wrapped component/function declarations like React.memo(() => ...) or forwardRef((...) => ...)
                if sub.type == "call_expression":
                    args = next((c for c in sub.children if c.type == "arguments"), None)
                    if args and any(arg.type in JS_FUNCTION_VALUE_TYPES for arg in args.children):
                        return True
        return False

    def _emit_function_chunks(
        self,
        raw_text: str,
        start_l: int,
        end_l: int,
        kind: str,
        parent_class: str,
        symbol_name: str,
        prefix: str,
        add_chunk_fn,
    ) -> None:
        """Emits a function/method chunk, splitting oversized functions while carrying the signature header."""
        lines = raw_text.splitlines()
        if len(lines) <= self.max_function_lines:
            add_chunk_fn(f"{prefix}{raw_text}", start_l, end_l, kind, parent_class, symbol_name)
            return

        signature_line = next((l.strip() for l in lines if l.strip() and not l.strip().startswith("@")), lines[0].strip())
        step = max(1, self.max_function_lines - self.fallback_overlap_lines)
        for idx in range(0, len(lines), step):
            part = lines[idx : idx + self.max_function_lines]
            if not part:
                continue
            p_start = start_l + idx
            p_end = start_l + idx + len(part) - 1
            header = prefix if idx == 0 else f"{prefix}# Function: {signature_line} (continued)\n"
            add_chunk_fn(header + "\n".join(part), p_start, p_end, kind, parent_class, symbol_name)
            if p_end >= end_l:
                break

    def _collect_uncovered_runs(self, file: LoadedFile, covered_lines: set[int]) -> list[CodeChunk]:
        """Collect contiguous runs of uncovered top-level lines (imports, constants, types, globals)."""
        file_lines = file.content.splitlines()
        runs: list[tuple[int, int]] = []  # (start_line, end_line), 1-indexed
        run_start = None
        for idx in range(1, len(file_lines) + 2):  # +1 sentinel to flush the last run
            uncovered = idx <= len(file_lines) and idx not in covered_lines
            if uncovered and run_start is None:
                run_start = idx
            elif not uncovered and run_start is not None:
                runs.append((run_start, idx - 1))
                run_start = None

        top_level: list[CodeChunk] = []
        for start, end in runs:
            # Trim blank lines at both edges so the line range is exact
            while start <= end and not file_lines[start - 1].strip():
                start += 1
            while end >= start and not file_lines[end - 1].strip():
                end -= 1
            # Split very long runs so no top-level code is dropped or oversized
            for s in range(start, end + 1, self.fallback_chunk_lines):
                e = min(s + self.fallback_chunk_lines - 1, end)
                body = "\n".join(file_lines[s - 1 : e])
                top_level.append(
                    CodeChunk(
                        file_path=file.file_path,
                        content=f"# File: {file.file_path} (top-level code)\n{body}",
                        start_line=s,
                        end_line=e,
                        node_type="module_preamble",
                    )
                )
        return top_level

    def chunk_python(self, file: LoadedFile) -> list[CodeChunk]:
        code_bytes = bytes(file.content, "utf8")
        tree = py_parser.parse(code_bytes)
        chunks: list[CodeChunk] = []
        covered_lines: set[int] = set()

        def add_chunk(
            content: str,
            start_l: int,
            end_l: int,
            kind: str,
            parent: str = "",
            symbol: str = "",
        ):
            chunks.append(
                CodeChunk(
                    file_path=file.file_path,
                    content=content,
                    start_line=start_l,
                    end_line=end_l,
                    node_type=kind,
                    parent_class=parent,
                    symbol_name=symbol,
                )
            )
            for line in range(start_l, end_l + 1):
                covered_lines.add(line)

        def visit(node, current_class: str = ""):
            wrapper, inner = self._unwrap_decorated(node)

            # 1. Class definition (handles both plain and decorated classes)
            if inner.type == "class_definition":
                class_name = self._get_class_name(inner, code_bytes)
                start_l = wrapper.start_point[0] + 1
                end_l = wrapper.end_point[0] + 1
                lines_count = (end_l - start_l) + 1

                # Small class -> keep as 1 atomic chunk
                if lines_count <= self.max_class_lines:
                    raw_text = self._get_node_text(wrapper, code_bytes)
                    content = f"# File: {file.file_path}\n{raw_text}"
                    add_chunk(content, start_l, end_l, "class", class_name, class_name)
                    return

                # Large class -> mark entire class span as covered so trailing lines/braces don't leak into module_preamble
                for line in range(start_l, end_l + 1):
                    covered_lines.add(line)

                # 1a. Emit class header (signature, docstrings, class attributes)
                body_node = next((c for c in inner.children if c.type == "block"), None)
                if body_node and body_node.children:
                    first_method = next(
                        (c for c in body_node.children if c.type in {"function_definition", "decorated_definition"}),
                        None,
                    )
                    header_end_byte = first_method.start_byte if first_method else wrapper.end_byte
                    header_text = code_bytes[wrapper.start_byte:header_end_byte].decode("utf8", errors="ignore").strip()

                    if header_text:
                        h_start = start_l
                        h_end = h_start + header_text.count("\n")
                        add_chunk(
                            f"# File: {file.file_path}\n# Class: {class_name} (Header)\n{header_text}",
                            h_start,
                            h_end,
                            "class_header",
                            class_name,
                            class_name,
                        )

                # 1b. Recurse into methods inside the class
                for child in (body_node.children if body_node else inner.children):
                    visit(child, current_class=class_name)
                return

            # 2. Function / Method definition
            if inner.type == "function_definition":
                start_l = wrapper.start_point[0] + 1
                end_l = wrapper.end_point[0] + 1
                raw_text = self._get_node_text(wrapper, code_bytes)
                kind = "method" if current_class else "function"
                func_name = self._get_function_name(inner, code_bytes)

                prefix = f"# File: {file.file_path}\n"
                if current_class:
                    prefix += f"# Class: {current_class}\n"

                self._emit_function_chunks(
                    raw_text=raw_text,
                    start_l=start_l,
                    end_l=end_l,
                    kind=kind,
                    parent_class=current_class,
                    symbol_name=func_name,
                    prefix=prefix,
                    add_chunk_fn=add_chunk,
                )
                return

            # Continue traversing
            for child in node.children:
                visit(child, current_class)

        visit(tree.root_node)

        # 3. Collect top-level code (imports, constants, app setup, globals)
        top_level = self._collect_uncovered_runs(file, covered_lines)
        return top_level + chunks

    def chunk_js_ts(self, file: LoadedFile, parser: Parser) -> list[CodeChunk]:
        """AST chunker for JavaScript, JSX, TypeScript, and TSX files."""
        code_bytes = bytes(file.content, "utf8")
        tree = parser.parse(code_bytes)
        chunks: list[CodeChunk] = []
        covered_lines: set[int] = set()

        def add_chunk(
            content: str,
            start_l: int,
            end_l: int,
            kind: str,
            parent: str = "",
            symbol: str = "",
        ):
            chunks.append(
                CodeChunk(
                    file_path=file.file_path,
                    content=content,
                    start_line=start_l,
                    end_line=end_l,
                    node_type=kind,
                    parent_class=parent,
                    symbol_name=symbol,
                )
            )
            for line in range(start_l, end_l + 1):
                covered_lines.add(line)

        def is_class_method_node(n) -> bool:
            if n.type in JS_METHOD_TYPES:
                return True
            if n.type in JS_FIELD_TYPES and self._is_js_function_field(n):
                return True
            return False

        def visit(node, current_class: str = ""):
            wrapper, inner = self._unwrap_js_export(node)

            # 1. Class definition (plain, exported, or abstract)
            if inner.type in JS_CLASS_TYPES:
                class_name = self._get_class_name(inner, code_bytes)
                start_l = wrapper.start_point[0] + 1
                end_l = wrapper.end_point[0] + 1
                lines_count = (end_l - start_l) + 1

                # Small class -> keep as 1 atomic chunk
                if lines_count <= self.max_class_lines:
                    raw_text = self._get_node_text(wrapper, code_bytes)
                    content = f"# File: {file.file_path}\n{raw_text}"
                    add_chunk(content, start_l, end_l, "class", class_name, class_name)
                    return

                # Large class -> mark entire class span as covered so closing braces/fields don't leak into module_preamble
                for line in range(start_l, end_l + 1):
                    covered_lines.add(line)

                # 1a. Emit class header (signature, fields before first method)
                body_node = next((c for c in inner.children if c.type == "class_body"), None)
                if body_node and body_node.children:
                    first_method = next((c for c in body_node.children if is_class_method_node(c)), None)
                    header_end_byte = first_method.start_byte if first_method else wrapper.end_byte
                    header_text = code_bytes[wrapper.start_byte:header_end_byte].decode("utf8", errors="ignore").strip()

                    if header_text:
                        h_start = start_l
                        h_end = h_start + header_text.count("\n")
                        add_chunk(
                            f"# File: {file.file_path}\n# Class: {class_name} (Header)\n{header_text}",
                            h_start,
                            h_end,
                            "class_header",
                            class_name,
                            class_name,
                        )

                # 1b. Recurse into methods inside the class
                for child in (body_node.children if body_node else inner.children):
                    visit(child, current_class=class_name)
                return

            # 2. Function / Method definition (declarations, class methods, arrow function fields/vars)
            is_func = (
                inner.type in JS_DIRECT_FUNC_TYPES
                or is_class_method_node(inner)
                or (not current_class and inner.type in JS_VAR_DECL_TYPES and self._is_js_function_var_decl(inner))
            )
            if is_func:
                start_l = wrapper.start_point[0] + 1
                end_l = wrapper.end_point[0] + 1
                raw_text = self._get_node_text(wrapper, code_bytes)
                kind = "method" if current_class else "function"
                func_name = self._get_function_name(inner, code_bytes)

                prefix = f"# File: {file.file_path}\n"
                if current_class:
                    prefix += f"# Class: {current_class}\n"

                self._emit_function_chunks(
                    raw_text=raw_text,
                    start_l=start_l,
                    end_l=end_l,
                    kind=kind,
                    parent_class=current_class,
                    symbol_name=func_name,
                    prefix=prefix,
                    add_chunk_fn=add_chunk,
                )
                return

            # Continue traversing
            for child in node.children:
                visit(child, current_class)

        visit(tree.root_node)

        # 3. Collect top-level code (imports, interfaces, type aliases, constants, exports)
        top_level = self._collect_uncovered_runs(file, covered_lines)
        return top_level + chunks

    def chunk_fallback(self, file: LoadedFile) -> list[CodeChunk]:
        """Fallback chunker for non-AST files (Markdown, YAML, JSON, TOML, text)."""
        lines = file.content.splitlines()
        if not lines:
            return []

        chunks: list[CodeChunk] = []
        step = max(1, self.fallback_chunk_lines - self.fallback_overlap_lines)

        for i in range(0, len(lines), step):
            slice_lines = lines[i : i + self.fallback_chunk_lines]
            if not slice_lines or not any(l.strip() for l in slice_lines):
                continue

            start_l = i + 1
            end_l = i + len(slice_lines)
            content = f"# File: {file.file_path}\n" + "\n".join(slice_lines)

            chunks.append(
                CodeChunk(
                    file_path=file.file_path,
                    content=content,
                    start_line=start_l,
                    end_line=end_l,
                    node_type="text",
                )
            )
            if end_l >= len(lines):
                break

        return chunks

    def chunk_file(self, file: LoadedFile) -> list[CodeChunk]:
        """Routes file to appropriate AST or text chunker based on extension."""
        if file.extension == ".py":
            return self.chunk_python(file)
        if file.extension in JS_TS_PARSERS:
            return self.chunk_js_ts(file, JS_TS_PARSERS[file.extension])
        return self.chunk_fallback(file)

    def chunk_all(self, files: list[LoadedFile]) -> list[CodeChunk]:
        all_chunks: list[CodeChunk] = []
        for file in files:
            all_chunks.extend(self.chunk_file(file))
        return all_chunks
