from dataclasses import dataclass
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


@dataclass
class CodeChunk:
    file_path: str
    content: str
    start_line: int
    end_line: int
    node_type: str        # e.g., "method", "function", "class", "class_header", "module_preamble", "text"
    parent_class: str = "" # e.g., "UserRepository"


class TreeSitterChunker:
    def __init__(self, max_class_lines: int = 50, fallback_chunk_lines: int = 60, fallback_overlap_lines: int = 10):
        self.max_class_lines = max_class_lines
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

        def add_chunk(content: str, start_l: int, end_l: int, kind: str, parent: str = ""):
            chunks.append(
                CodeChunk(
                    file_path=file.file_path,
                    content=content,
                    start_line=start_l,
                    end_line=end_l,
                    node_type=kind,
                    parent_class=parent,
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
                    add_chunk(content, start_l, end_l, "class", class_name)
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

                prefix = f"# File: {file.file_path}\n"
                if current_class:
                    prefix += f"# Class: {current_class}\n"

                add_chunk(f"{prefix}{raw_text}", start_l, end_l, kind, current_class)
                return

            # Continue traversing
            for child in node.children:
                visit(child, current_class)

        visit(tree.root_node)

        # 3. Collect top-level code (imports, constants, app setup, globals)
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
        return self.chunk_fallback(file)

    def chunk_all(self, files: list[LoadedFile]) -> list[CodeChunk]:
        all_chunks: list[CodeChunk] = []
        for file in files:
            all_chunks.extend(self.chunk_file(file))
        return all_chunks
