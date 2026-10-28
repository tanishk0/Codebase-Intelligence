from collections import defaultdict
from pathlib import Path
from ingestion.chunker import CodeChunk
from retrieval.llm import NvidiaChatClient


def _extract_signature_and_doc(chunk: CodeChunk) -> str:
    """Extracts the declaration signature and first docstring line from a code chunk."""
    code_lines = [
        line.strip()
        for line in chunk.content.splitlines()
        if line.strip() and not line.startswith("# File:") and not line.startswith("# Class:")
    ]
    if not code_lines:
        return chunk.symbol_name or chunk.node_type

    # Find first non-decorator signature line
    sig = next((l for l in code_lines if not l.startswith("@")), code_lines[0])
    sig = sig[:120]

    # Look for a docstring line right after the signature
    doc = ""
    for line in code_lines[1:5]:
        cleaned = line.strip("\"' \t")
        if cleaned and not cleaned.startswith("#"):
            if line.startswith(('"""', "'''", "/**", "//", "#")):
                doc = f" — {cleaned[:100]}"
                break
    return f"{sig}{doc}"


def build_file_outline(file_path: str, file_chunks: list[CodeChunk]) -> str:
    """Builds a compact structural outline of a file from its AST chunks (zero LLM calls)."""
    if not file_chunks:
        return f"# File Summary: {file_path}"

    classes: list[str] = []
    functions: list[str] = []
    methods_by_class: dict[str, list[str]] = defaultdict(list)
    preamble_preview: list[str] = []

    for c in file_chunks:
        if c.node_type == "module_preamble" and not preamble_preview:
            lines = [
                l.strip()
                for l in c.content.splitlines()
                if l.strip() and not l.startswith("# File:")
            ]
            preamble_preview = lines[:6]
        elif c.node_type in {"class", "class_header"}:
            classes.append(_extract_signature_and_doc(c))
        elif c.node_type == "function":
            functions.append(_extract_signature_and_doc(c))
        elif c.node_type == "method":
            parent = c.parent_class or "Class"
            methods_by_class[parent].append(c.symbol_name or _extract_signature_and_doc(c))

    parts = [f"# File Summary: {file_path}"]
    if preamble_preview:
        parts.append("Imports/Setup: " + "; ".join(preamble_preview[:4]))
    if classes:
        parts.append("Classes: " + " | ".join(classes))
    for cls_name, methods in methods_by_class.items():
        unique_methods = list(dict.fromkeys(methods))
        parts.append(f"Methods of {cls_name}: {', '.join(unique_methods)}")
    if functions:
        parts.append("Functions: " + " | ".join(functions))

    # Fallback for non-AST files (Markdown, configs, JSON)
    if len(parts) == 1:
        first_chunk = file_chunks[0]
        preview = [
            l.strip()
            for l in first_chunk.content.splitlines()
            if l.strip() and not l.startswith("# File:")
        ][:8]
        parts.append("Preview: " + " / ".join(preview))

    return "\n".join(parts)


class RepoSummarizer:
    """Generates file-level summary chunks and a repository-wide architectural overview."""

    def __init__(
        self,
        llm_client: NvidiaChatClient | None = None,
        files_per_llm_batch: int = 6,
    ) -> None:
        self.llm = llm_client
        self.files_per_llm_batch = files_per_llm_batch

    def build_file_summary_chunks(
        self,
        chunks: list[CodeChunk],
        *,
        use_llm: bool = False,
    ) -> list[CodeChunk]:
        """Creates one `file_summary` CodeChunk per source file from its AST outline.

        When `use_llm=True` and an `NvidiaChatClient` is configured, batches multiple file outlines per
        LLM request to prepend a concise natural-language summary without blowing the RPM budget.
        """
        by_file: dict[str, list[CodeChunk]] = defaultdict(list)
        for chunk in chunks:
            if chunk.node_type != "file_summary":
                by_file[chunk.file_path].append(chunk)

        outlines: dict[str, str] = {
            fp: build_file_outline(fp, f_chunks) for fp, f_chunks in sorted(by_file.items())
        }

        llm_descriptions: dict[str, str] = {}
        if use_llm and self.llm is not None and outlines:
            items = list(outlines.items())
            for start in range(0, len(items), self.files_per_llm_batch):
                batch = items[start : start + self.files_per_llm_batch]
                prompt_block = "\n\n".join(f"### {fp}\n{outline}" for fp, outline in batch)
                messages = [
                    {
                        "role": "system",
                        "content": (
                            "You summarize code files from their structural outlines. "
                            "Return ONLY a JSON object mapping each exact file path to a 1-2 sentence "
                            "summary of its responsibility and key symbols."
                        ),
                    },
                    {"role": "user", "content": prompt_block},
                ]
                try:
                    parsed = self.llm.complete_json(messages, use_fast_model=True, max_tokens=512)
                    if isinstance(parsed, dict):
                        for fp, desc in parsed.items():
                            if isinstance(desc, str) and desc.strip():
                                llm_descriptions[fp] = desc.strip()
                except Exception:
                    # Fallback cleanly to the structural outline if the LLM call fails or times out
                    pass

        summary_chunks: list[CodeChunk] = []
        for fp, f_chunks in sorted(by_file.items()):
            max_line = max((c.end_line for c in f_chunks), default=1)
            outline = outlines[fp]
            desc = llm_descriptions.get(fp)
            content = f"{outline}\nSummary: {desc}" if desc else outline
            summary_chunks.append(
                CodeChunk(
                    file_path=fp,
                    content=content,
                    start_line=1,
                    end_line=max_line,
                    node_type="file_summary",
                    parent_class="",
                    symbol_name=Path(fp).name,
                )
            )
        return summary_chunks

    def build_repo_summary(
        self,
        repo_url: str,
        file_summary_chunks: list[CodeChunk],
        *,
        use_llm: bool = False,
    ) -> str:
        """Builds a concise repository-level overview from the file tree and file summaries."""
        file_paths = [c.file_path for c in file_summary_chunks]
        tree_block = "Files:\n" + "\n".join(f"- {fp}" for fp in file_paths[:60])
        outlines_block = "\n\n".join(c.content for c in file_summary_chunks[:25])
        structural_overview = f"Repository: {repo_url}\n{tree_block}\n\nKey Modules:\n{outlines_block[:2500]}"

        if not use_llm or self.llm is None:
            return structural_overview

        messages = [
            {
                "role": "system",
                "content": (
                    "You are a senior software architect. Given a repository's file list and module outlines, "
                    "write a concise (~150-250 word) architectural overview covering its purpose, main components, "
                    "and how data flows through the system."
                ),
            },
            {"role": "user", "content": structural_overview},
        ]
        try:
            llm_summary = self.llm.complete(messages, use_fast_model=True, max_tokens=400)
            if llm_summary:
                return f"Repository: {repo_url}\n\nArchitecture Overview:\n{llm_summary}\n\n{tree_block}"
        except Exception:
            pass
        return structural_overview

