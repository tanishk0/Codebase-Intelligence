from pathlib import Path

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


def should_load_file(file_path: str) -> bool:
    path = Path(file_path)

    if any(part in IGNORED_DIRS for part in path.parts):
        return False

    return path.suffix.lower() in SUPPORTED_EXTENSIONS


def discover_files(repo_path: Path) -> list[Path]:
    return [
        path
        for path in repo_path.rglob("*")
        if path.is_file() and should_load_file(str(path.relative_to(repo_path)))
    ]