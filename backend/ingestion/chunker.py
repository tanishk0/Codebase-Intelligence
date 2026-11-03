from dataclasses import dataclass, field
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

CLASS_TYPES = {"class_definition", "class_declaration", "abstract_class_declaration"}
CLASS_BODY_TYPES = {"block", "class_body"}
JS_FUNCTION_VALUE_TYPES = {"arrow_function", "function_expression", "generator_function"}
JS_DIRECT_FUNC_TYPES = {"function_declaration", "generator_function_declaration"}
JS_METHOD_TYPES = {"method_definition", "abstract_method_signature"}
JS_FIELD_TYPES = {"field_definition", "public_field_definition"}
JS_VAR_DECL_TYPES = {"lexical_declaration", "variable_declaration"}
UNWRAP_INNER_TYPES = CLASS_TYPES | {"function_definition"} | JS_DIRECT_FUNC_TYPES | JS_VAR_DECL_TYPES

_CAMEL_BOUNDARY_1 = re.compile(r"([a-z0-9])([A-Z])")
_CAMEL_BOUNDARY_2 = re.compile(r"([A-Z]+)([A-Z][a-z])")
_IDENT_RE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{2,}")

# Bump these when the chunker's output or the injected headers change. They feed the
# index pipeline fingerprint, so a bump forces a rebuild instead of silently serving
# chunks produced by the previous implementation.
CHUNKER_VERSION = 2
SEARCH_TEXT_VERSION = 1
HEADER_FORMAT_VERSION = 1

SYNTHETIC_HEADER_PREFIXES = (
    "# File:",
    "# Class:",
    "# Function:",
    "# Imports:",
    "# Imported by:",
    "# Inherits from:",
    "# Calls:",
    "# Called by:",
)


def get_node_text(node, code_bytes: bytes) -> str:
    """Slices the UTF-8 source text for a Tree-sitter AST node."""
    return code_bytes[node.start_byte : node.end_byte].decode("utf8", errors="ignore")


def split_chunk_headers(content: str) -> tuple[list[str], list[str]]:
    """Splits a chunk's content into (leading synthetic `# ...` header lines, raw code lines)."""
    headers: list[str] = []
    body: list[str] = []
    for line in content.splitlines():
        if not body and line.startswith(SYNTHETIC_HEADER_PREFIXES):
            headers.append(line)
        else:
            body.append(line)
    return headers, body


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
    imports: list[str] = field(default_factory=list)
    imported_by: list[str] = field(default_factory=list)
    calls: list[str] = field(default_factory=list)
    called_by: list[str] = field(default_factory=list)
    inherits_from: list[str] = field(default_factory=list)

    def code_lines(self) -> list[str]:
        """Returns raw code lines with synthetic `# File:` / `# Class:` / `# Calls:` headers stripped."""
        return split_chunk_headers(self.content)[1]


def build_search_text(chunk: CodeChunk) -> str:
    """Builds keyword-rich text combining file path, symbols, dependency edges, split identifiers, and content."""
    path_words = re.sub(r"[/._\-]+", " ", chunk.file_path)
    dep_symbols = re.sub(r"[.]+", " ", " ".join(chunk.calls + chunk.called_by + chunk.inherits_from))
    dep_files = " ".join(chunk.imports + chunk.imported_by)
    base = f"{chunk.file_path} {path_words} {chunk.parent_class} {chunk.symbol_name} {dep_symbols} {dep_files}"
    split_tokens = split_identifier_tokens(f"{base} {chunk.content}")
    return " ".join(p for p in (base, split_tokens, chunk.content) if p)


class TreeSitterChunker:
    def __init__(
        self,
        max_class_lines: int = 50,
        max_function_lines: int = 120,
        fallback_chunk_lines: int = 60,
        fallback_overlap_lines: int = 10,
    ) -> None:
        self.max_class_lines = max_class_lines
        self.max_function_lines = max_function_lines
        self.fallback_chunk_lines = fallback_chunk_lines
        self.fallback_overlap_lines = fallback_overlap_lines

    def pipeline_params(self) -> dict[str, int]:
        """Returns the parameters that change the produced chunk set (for index invalidation)."""
        return {
            "max_class_lines": self.max_class_lines,
            "max_function_lines": self.max_function_lines,
            "fallback_chunk_lines": self.fallback_chunk_lines,
            "fallback_overlap_lines": self.fallback_overlap_lines,
        }

    @staticmethod
    def _unwrap_node(node):
        """Unwraps Python `decorated_definition` or JS/TS `export_statement` around a declaration."""
        if node.type in {"decorated_definition", "export_statement"}:
            for child in node.children:
                if child.type in UNWRAP_INNER_TYPES:
                    return node, child
        return node, node

    @staticmethod
    def _get_symbol_name(node, code_bytes: bytes, default: str = "") -> str:
        for child in node.children:
            if child.type in {"identifier", "property_identifier", "type_identifier"}:
                return get_node_text(child, code_bytes)
            if child.type == "variable_declarator":
                for sub in child.children:
                    if sub.type in {"identifier", "property_identifier"}:
                        return get_node_text(sub, code_bytes)
        return default

    @staticmethod
    def _is_js_function_var_decl(decl_node) -> bool:
        """True if a lexical/variable declaration defines a function (e.g., const fn = () => {} or React.memo(() => {}))."""
        for child in decl_node.children:
            if child.type != "variable_declarator":
                continue
            for sub in child.children:
                if sub.type in JS_FUNCTION_VALUE_TYPES:
                    return True
                if sub.type == "call_expression":
                    args = next((c for c in sub.children if c.type == "arguments"), None)
                    if args and any(arg.type in JS_FUNCTION_VALUE_TYPES for arg in args.children):
                        return True
        return False

    def _is_callable_node(self, node, in_class: bool = False) -> bool:
        """True if `node` is a Python/JS/TS function, method, or arrow-function declaration."""
        if node.type == "function_definition" or node.type in JS_DIRECT_FUNC_TYPES:
            return True
        if node.type in JS_METHOD_TYPES:
            return True
        if node.type in JS_FIELD_TYPES:
            return any(c.type in JS_FUNCTION_VALUE_TYPES for c in node.children)
        return not in_class and node.type in JS_VAR_DECL_TYPES and self._is_js_function_var_decl(node)

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

        sig_line = next((l.strip() for l in lines if l.strip() and not l.strip().startswith("@")), lines[0].strip())
        step = max(1, self.max_function_lines - self.fallback_overlap_lines)
        for idx in range(0, len(lines), step):
            part = lines[idx : idx + self.max_function_lines]
            if not part:
                continue
            p_start, p_end = start_l + idx, start_l + idx + len(part) - 1
            header = prefix if idx == 0 else f"{prefix}# Function: {sig_line} (continued)\n"
            add_chunk_fn(header + "\n".join(part), p_start, p_end, kind, parent_class, symbol_name)
            if p_end >= end_l:
                break

    def _collect_uncovered_runs(self, file: LoadedFile, covered_lines: set[int]) -> list[CodeChunk]:
        """Collects contiguous runs of uncovered top-level lines (imports, constants, types, globals)."""
        file_lines = file.content.splitlines()
        runs: list[tuple[int, int]] = []
        run_start = None
        for idx in range(1, len(file_lines) + 2):
            uncovered = idx <= len(file_lines) and idx not in covered_lines
            if uncovered and run_start is None:
                run_start = idx
            elif not uncovered and run_start is not None:
                runs.append((run_start, idx - 1))
                run_start = None

        top_level: list[CodeChunk] = []
        for start, end in runs:
            while start <= end and not file_lines[start - 1].strip():
                start += 1
            while end >= start and not file_lines[end - 1].strip():
                end -= 1
            for s in range(start, end + 1, self.fallback_chunk_lines):
                e = min(s + self.fallback_chunk_lines - 1, end)
                body = "\n".join(file_lines[s - 1 : e])
                top_level.append(
                    CodeChunk(file.file_path, f"# File: {file.file_path} (top-level code)\n{body}", s, e, "module_preamble")
                )
        return top_level

    def _chunk_ast(self, file: LoadedFile, parser: Parser) -> list[CodeChunk]:
        """Unified Tree-sitter AST chunker for Python, JavaScript, JSX, TypeScript, and TSX."""
        code_bytes = file.content.encode("utf8")
        tree = parser.parse(code_bytes)
        chunks: list[CodeChunk] = []
        covered_lines: set[int] = set()

        def add_chunk(content: str, start_l: int, end_l: int, kind: str, parent: str = "", symbol: str = "") -> None:
            chunks.append(CodeChunk(file.file_path, content, start_l, end_l, kind, parent, symbol))
            covered_lines.update(range(start_l, end_l + 1))

        def visit(node, current_class: str = "") -> None:
            wrapper, inner = self._unwrap_node(node)

            # 1. Class definition (plain, decorated, exported, or abstract)
            if inner.type in CLASS_TYPES:
                class_name = self._get_symbol_name(inner, code_bytes, default="UnknownClass")
                start_l, end_l = wrapper.start_point[0] + 1, wrapper.end_point[0] + 1

                if (end_l - start_l) + 1 <= self.max_class_lines:
                    raw_text = get_node_text(wrapper, code_bytes)
                    add_chunk(f"# File: {file.file_path}\n{raw_text}", start_l, end_l, "class", class_name, class_name)
                    return

                covered_lines.update(range(start_l, end_l + 1))
                body_node = next((c for c in inner.children if c.type in CLASS_BODY_TYPES), None)
                first_method = None
                if body_node and body_node.children:
                    first_method = next(
                        (c for c in body_node.children if self._is_callable_node(self._unwrap_node(c)[1], in_class=True)),
                        None,
                    )
                    header_end_byte = first_method.start_byte if first_method else wrapper.end_byte
                    header_text = code_bytes[wrapper.start_byte : header_end_byte].decode("utf8", errors="ignore").strip()
                    if header_text:
                        h_end = start_l + header_text.count("\n")
                        add_chunk(
                            f"# File: {file.file_path}\n# Class: {class_name} (Header)\n{header_text}",
                            start_l,
                            h_end,
                            "class_header",
                            class_name,
                            class_name,
                        )

                first_method_start = first_method.start_point[0] + 1 if first_method else None

                for child in (body_node.children if body_node else inner.children):
                    child_inner = self._unwrap_node(child)[1]
                    child_start = child.start_point[0] + 1
                    if (
                        first_method_start is not None
                        and child_start >= first_method_start
                        and child.is_named
                        and not self._is_callable_node(child_inner, in_class=True)
                    ):
                        # Large-class splitting used to mark these lines covered without
                        # emitting them, losing fields declared between methods.
                        raw_text = get_node_text(child, code_bytes)
                        if raw_text.strip():
                            add_chunk(
                                f"# File: {file.file_path}\n# Class: {class_name}\n{raw_text}",
                                child_start,
                                child.end_point[0] + 1,
                                "class_member",
                                class_name,
                                class_name,
                            )
                        continue
                    visit(child, current_class=class_name)
                return

            # 2. Function / Method definition
            if self._is_callable_node(inner, in_class=bool(current_class)):
                start_l, end_l = wrapper.start_point[0] + 1, wrapper.end_point[0] + 1
                raw_text = get_node_text(wrapper, code_bytes)
                kind = "method" if current_class else "function"
                func_name = self._get_symbol_name(inner, code_bytes)
                prefix = f"# File: {file.file_path}\n" + (f"# Class: {current_class}\n" if current_class else "")
                self._emit_function_chunks(raw_text, start_l, end_l, kind, current_class, func_name, prefix, add_chunk)
                return

            for child in node.children:
                visit(child, current_class)

        visit(tree.root_node)
        return self._collect_uncovered_runs(file, covered_lines) + chunks

    def chunk_python(self, file: LoadedFile) -> list[CodeChunk]:
        return self._chunk_ast(file, py_parser)

    def chunk_js_ts(self, file: LoadedFile, parser: Parser) -> list[CodeChunk]:
        return self._chunk_ast(file, parser)

    def chunk_fallback(self, file: LoadedFile) -> list[CodeChunk]:
        """Fallback chunker for non-AST files (Markdown, YAML, JSON, TOML, SQL, text)."""
        lines = file.content.splitlines()
        if not lines:
            return []

        chunks: list[CodeChunk] = []
        step = max(1, self.fallback_chunk_lines - self.fallback_overlap_lines)
        for i in range(0, len(lines), step):
            slice_lines = lines[i : i + self.fallback_chunk_lines]
            if not slice_lines or not any(l.strip() for l in slice_lines):
                continue
            start_l, end_l = i + 1, i + len(slice_lines)
            content = f"# File: {file.file_path}\n" + "\n".join(slice_lines)
            chunks.append(CodeChunk(file.file_path, content, start_l, end_l, "text"))
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
        return [chunk for file in files for chunk in self.chunk_file(file)]
