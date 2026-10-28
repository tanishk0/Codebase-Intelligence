import tempfile
from pathlib import Path
from urllib.parse import urlparse
from git import Repo
from git.exc import GitCommandError


def validate_github_url(url: str) -> None:
    """Ensure URL is a valid public HTTPS GitHub repository."""
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("Only HTTPS GitHub URLs are supported.")
    if parsed.hostname not in {"github.com", "www.github.com"}:
        raise ValueError("URL must be from github.com.")
    if not parsed.path.strip("/"):
        raise ValueError("Invalid repository path.")


class RepoCloner:
    """Clones a remote repository to a temporary directory for ingestion."""

    def __init__(self, git_url: str, branch: str | None = None):
        validate_github_url(git_url)
        self.git_url = git_url
        self.branch = branch
        self._temp_dir: tempfile.TemporaryDirectory | None = None

    def clone(self) -> Path:
        self._temp_dir = tempfile.TemporaryDirectory()
        target_path = Path(self._temp_dir.name)

        try:
            # depth=1 downloads only the latest commit, minimizing disk and network usage.
            # When branch is None, git automatically clones the remote's default branch (main, master, etc.).
            clone_kwargs = {"depth": 1, "single_branch": True}
            if self.branch:
                clone_kwargs["branch"] = self.branch

            Repo.clone_from(
                url=self.git_url,
                to_path=target_path,
                **clone_kwargs,
            )
            return target_path
        except GitCommandError as exc:
            self.cleanup()
            raise RuntimeError(f"Failed to clone repository: {exc}") from exc

    def cleanup(self) -> None:
        """Removes the temporary directory and all cloned files."""
        if self._temp_dir is not None:
            self._temp_dir.cleanup()
            self._temp_dir = None
