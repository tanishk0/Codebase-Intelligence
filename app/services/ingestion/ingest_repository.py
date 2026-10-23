from pathlib import Path

from app.services.ingestion.git_loader import clone_repository
from app.services.ingestion.file_discovery import discover_files
from urllib.parse import urlparse

from git.exc import GitCommandError


class IngestionError(Exception):
    """Raised when repository ingestion fails."""

def validate_git_url(git_url: str) -> None:
    parsed = urlparse(git_url)

    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.port not in (None, 443)
        or parsed.hostname not in {"github.com", "www.github.com"}
    ):
        raise ValueError("Only public HTTPS GitHub URLs are allowed")


def ingest_repository(
    git_url: str,
    branch: str = "main",
) -> tuple[list[Path], object]:
    validate_git_url(git_url)
    repo, temp_dir = clone_repository(git_url, branch)
    try:
        repo, temp_dir = clone_repository(git_url, branch)
    except GitCommandError as exc:
        raise IngestionError(
            "Could not clone repository. Check the URL, branch, and access."
        ) from exc
from pathlib import Path

from langchain_community.document_loaders import GitLoader

from app.services.ingestion.git_loader import clone_repository


IGNORED_DIRS = {
    ".git",
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    "dist",
    "build",
    ".next",
}

SUPPORTED_EXTENSIONS = {".py", ".js", ".jsx", ".ts", ".tsx"}

MAX_FILE_SIZE_BYTES = 2_000_000  # 2 MB
MAX_FILES = 5_000
MAX_TOTAL_SIZE_BYTES = 50_000_000  # 50 MB


def should_load_file(file_path: str) -> bool:
    path = Path(file_path)

    if any(part in IGNORED_DIRS for part in path.parts):
        return False

    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def ingest_repository(git_url: str, branch: str = "main"):
    repo, temp_dir = clone_repository(git_url, branch)

    try:
        loader = GitLoader(
            repo_path=repo.working_tree_dir,
            branch=branch,
            file_filter=should_load_file,
        )
        documents = loader.load()
        if len(documents) > MAX_FILES:
            raise ValueError("Repository exceeds the maximum file count")

        return extract_file_records(
            documents,
            Path(repo.working_tree_dir),
        )
    finally:
        repo.close()
        temp_dir.cleanup()

def extract_file_records(documents, repo_root: Path):
    records = []
    total_size = 0

    for document in documents:
        source = document.metadata.get("source")
        if not source:
            continue

        path = Path(source)

        try:
            relative_path = path.resolve().relative_to(repo_root.resolve())
        except ValueError:
            continue

        content = document.page_content
        size_bytes = len(content.encode("utf-8"))

        if size_bytes > MAX_FILE_SIZE_BYTES:
            continue

        if total_size + size_bytes > MAX_TOTAL_SIZE_BYTES:
            break

        total_size += size_bytes

        records.append({
            "file_path": relative_path.as_posix(),
            "content": content,
            "extension": path.suffix.lower(),
            "size_bytes": size_bytes,
        })

    return records