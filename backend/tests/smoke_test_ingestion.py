from collections import Counter
from pathlib import Path
import sys

# Ensure backend root is on sys.path when run directly
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.chunker import TreeSitterChunker
from ingestion.git_clone import RepoCloner
from ingestion.loader import load_repository_files


def run_smoke_test(repo_url: str = "https://github.com/psf/requests", branch: str = "main") -> None:
    print(f"Cloning {repo_url}...")

    cloner = RepoCloner(repo_url, branch=branch)
    try:
        repo_dir = cloner.clone()
        files = load_repository_files(repo_dir)
        print(f"Loaded {len(files)} files.")

        chunks = TreeSitterChunker().chunk_all(files)
        print(f"Created {len(chunks)} chunks: {dict(Counter(c.node_type for c in chunks))}\n")

        # Show the chunks for one file so you can eyeball the line ranges
        sample_file = "src/requests/sessions.py"
        for c in [c for c in chunks if c.file_path == sample_file][:8]:
            label = f"{c.parent_class}." if c.parent_class else ""
            code_lines = [
                l
                for l in c.content.splitlines()
                if l.strip() and not l.startswith("# File:") and not l.startswith("# Class:")
            ]
            first_code_line = code_lines[0][:60] if code_lines else ""
            print(f"[{c.node_type:15}] L{c.start_line}-L{c.end_line:<5} {label}{first_code_line.strip()}")
    finally:
        cloner.cleanup()
        print("\nCleaned up temporary clone directory.")


if __name__ == "__main__":
    run_smoke_test()

