import re 
from pathlib import Path

MAX_LINES_PER_CHUNK = 150
CHUNK_OVERLAP = 40
MAX_CHARS_PER_CHUNK = 12_000

LANGUAGE_BY_EXTENSION = {
    ".py": "python",
    ".js": "javascript",
    ".jsx": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
}

BOUNDARY_PATTERNS = {
    "python": re.compile(r"^\s*(?:async\s+)?(?:def|class)\s+\w+", re.MULTILINE),
    "javascript": re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?"
        r"(?:async\s+)?(?:function|class)\s+\w+|"
        r"^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>",
        re.MULTILINE,
    ),
    "typescript": re.compile(
        r"^\s*(?:export\s+)?(?:default\s+)?"
        r"(?:abstract\s+)?(?:async\s+)?(?:function|class|interface|type|enum)\s+\w+|"
        r"^\s*(?:export\s+)?(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?(?:\([^)]*\)|\w+)\s*=>",
        re.MULTILINE,
    ),
}

SYMBOL_PATTERN = re.compile(
    r"^\s*(?:export\s+)?(?:async\s+)?"
    r"(?:def|class|function|interface|type|enum)\s+(\w+)",
    re.MULTILINE,
)


def chunk_code(
    content: str,
    file_path: str,
    max_lines: int = MAX_LINES_PER_CHUNK,
    overlap: int = CHUNK_OVERLAP,
    max_chars: int = MAX_CHARS_PER_CHUNK,
) -> list[dict]:
    """Split source code into bounded chunks with source metadata."""
    if max_lines < 1 or max_chars < 1:
        raise ValueError("Chunk size limits must be positive")

    if overlap < 0 or overlap >= max_lines:
        raise ValueError("Overlap must be non-negative and smaller than max_lines")

    if not content.strip():
        return []

    extension = Path(file_path).suffix.lower()
    language = LANGUAGE_BY_EXTENSION.get(extension, "unknown")
    lines = content.splitlines()
    boundaries = BOUNDARY_PATTERNS.get(
        language, BOUNDARY_PATTERNS["python"]
    )

    declaration_lines = {
        len(lines[:match.start()].splitlines())
        for match in boundaries.finditer(content)
    }

    chunks = []
    start = 0

    while start < len(lines):
        end_limit = min(start + max_lines, len(lines))
        end = end_limit

        # Prefer ending immediately before a declaration near the size limit.
        candidates = [
            line_number
            for line_number in declaration_lines
            if start < line_number < end_limit
            and "\n".join(lines[start:line_number]).strip()
        ]

        if end_limit < len(lines) and candidates:
            end = max(candidates)

        # Enforce the character limit without exceeding it.
        while end > start + 1 and len("\n".join(lines[start:end])) > max_chars:
            end -= 1

        # A single source line can exceed max_chars; split it safely.
        if end == start + 1 and len(lines[start]) > max_chars:
            line = lines[start]
            for offset in range(0, len(line), max_chars):
                piece = line[offset:offset + max_chars]
                chunks.append({
                    "file_path": file_path,
                    "start_line": start + 1,
                    "end_line": start + 1,
                    "content": piece,
                    "language": language,
                    "symbols": SYMBOL_PATTERN.findall(piece),
                })
            start += 1
            continue

        chunk_lines = lines[start:end]
        chunk_text = "\n".join(chunk_lines)

        if chunk_text.strip():
            chunks.append({
                "file_path": file_path,
                "start_line": start + 1,
                "end_line": end,
                "content": chunk_text,
                "language": language,
                "symbols": SYMBOL_PATTERN.findall(chunk_text),
            })

        if end >= len(lines):
            break

        start = max(start + 1, end - overlap)

    return chunks