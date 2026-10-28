from dataclasses import dataclass
from pathlib import Path
from config import settings


@dataclass
class LoadedFile:
    file_path: str   # Relative path (e.g. "backend/main.py")
    content: str     # Raw text content of the code file
    extension: str   # File extension (e.g. ".py")
    size_bytes: int  # Size in bytes


def is_text_file(path: Path) -> bool:
    """Quick check to avoid reading binary files."""
    try:
        with open(path, "tr", encoding="utf-8") as f:
            f.read(1024)
            return True
    except UnicodeDecodeError:
        return False


def load_repository_files(repo_root: Path) -> list[LoadedFile]:
    """Scans the cloned directory and extracts all code files adhering to size and type limits."""
    loaded_files: list[LoadedFile] = []

    for path in repo_root.rglob("*"):
        if not path.is_file():
            continue

        # 1. Skip ignored directories (.git, node_modules, etc.)
        if any(part in settings.IGNORED_DIRS for part in path.parts):
            continue

        # 2. Skip ignored extensions (.lock, .png, etc.)
        if path.suffix.lower() in settings.IGNORED_EXTENSIONS:
            continue

        # 3. Check file size
        size = path.stat().st_size
        if size == 0 or size > settings.MAX_FILE_SIZE_BYTES:
            continue

        # 4. Check if text-readable
        if not is_text_file(path):
            continue

        # 5. Read content and record
        try:
            content = path.read_text(encoding="utf-8", errors="ignore")
            relative_path = path.relative_to(repo_root).as_posix()

            loaded_files.append(
                LoadedFile(
                    file_path=relative_path,
                    content=content,
                    extension=path.suffix.lower(),
                    size_bytes=size,
                )
            )
        except Exception:
            continue

        if len(loaded_files) >= settings.MAX_TOTAL_FILES:
            break

    return loaded_files
