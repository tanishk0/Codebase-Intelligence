from dataclasses import dataclass
import hashlib
from pathlib import Path
from config import settings


@dataclass
class LoadedFile:
    file_path: str          # Relative path (e.g. "backend/main.py")
    content: str            # Raw text content of the code file
    extension: str          # File extension (e.g. ".py")
    size_bytes: int         # Size in bytes
    content_hash: str = ""  # SHA-256 hex digest of raw file bytes

    def __post_init__(self) -> None:
        if not self.content_hash and self.content is not None:
            self.content_hash = hashlib.sha256(self.content.encode("utf-8", errors="ignore")).hexdigest()


def build_file_manifest(files: list[LoadedFile]) -> dict[str, str]:
    """Builds a deterministic {file_path: sha256_hex} manifest for incremental sync diffing."""
    return {f.file_path: f.content_hash for f in sorted(files, key=lambda x: x.file_path)}


def is_text_file(path: Path) -> bool:
    """Quick check to avoid reading binary files."""
    try:
        with open(path, "tr", encoding="utf-8") as f:
            f.read(1024)
            return True
    except UnicodeDecodeError:
        return False


def is_safe_path(path: Path, resolved_root: Path) -> bool:
    """Reject symlinks and anything that resolves outside the repository root.

    Cloned repos are untrusted input: a malicious repo could ship a symlink such as
    `notes.txt -> ~/.ssh/id_rsa` to get host files read, embedded, and stored.
    """
    if path.is_symlink():
        return False
    try:
        return path.resolve().is_relative_to(resolved_root)
    except OSError:
        return False


def load_repository_files(
    repo_root: Path,
    max_total_bytes: int | None = None,
) -> list[LoadedFile]:
    """Scans the cloned directory and extracts all code files adhering to size and type limits."""
    loaded_files: list[LoadedFile] = []
    resolved_root = repo_root.resolve()
    total_bytes = 0
    byte_budget = max_total_bytes if max_total_bytes is not None else settings.MAX_TOTAL_BYTES

    # Sorted so that hitting MAX_TOTAL_FILES or MAX_TOTAL_BYTES selects the same subset on every run.
    # With raw rglob order (filesystem-dependent) a repo above the cap produced different manifests
    # each sync, which looked like a mass rename and re-embedded the whole index.
    for path in sorted(repo_root.rglob("*")):
        # 0. Security: skip symlinks and paths escaping the repo root
        if not is_safe_path(path, resolved_root):
            continue

        if not path.is_file():
            continue

        # 1. Skip ignored directories (.git, node_modules, etc.)
        if any(part in settings.IGNORED_DIRS for part in path.parts):
            continue

        # 2. Skip ignored extensions (.lock, .png, etc.)
        if path.suffix.lower() in settings.IGNORED_EXTENSIONS:
            continue

        # 3. Check file size and cumulative repository byte budget
        size = path.stat().st_size
        if size == 0 or size > settings.MAX_FILE_SIZE_BYTES:
            continue

        # 4. Check if text-readable
        if not is_text_file(path):
            continue

        # 5. Read raw bytes once, compute SHA-256 hash, and decode UTF-8 text
        try:
            raw_bytes = path.read_bytes()
            content_hash = hashlib.sha256(raw_bytes).hexdigest()
            content = raw_bytes.decode("utf-8", errors="ignore")
            relative_path = path.relative_to(repo_root).as_posix()

            loaded_files.append(
                LoadedFile(
                    file_path=relative_path,
                    content=content,
                    extension=path.suffix.lower(),
                    size_bytes=size,
                    content_hash=content_hash,
                )
            )
        except Exception:
            continue

        if len(loaded_files) >= settings.MAX_TOTAL_FILES:
            break

    return loaded_files
