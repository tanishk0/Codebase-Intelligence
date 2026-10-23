import tempfile
from pathlib import Path
from git import Repo

def clone_repository(
        git_url: str,
        branch: str = "main"
) -> tuple[Repo, tempfile.TemporaryDirectory]:
    temp_dir = tempfile.TemporaryDirectory()
    destination = Path(temp_dir.name) / "repo"

    try:
        repo = Repo.clone_from(
            git_url,
            destination,
            branch=branch,
            depth=1,
        )
        return repo, temp_dir
    except Exception:
        temp_dir.cleanup()
        raise