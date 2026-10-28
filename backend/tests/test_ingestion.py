from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.git_clone import validate_github_url
from ingestion.loader import is_safe_path, load_repository_files


class TestIngestionHelpers(unittest.TestCase):
    def test_validate_github_url_accepts_valid_https(self) -> None:
        validate_github_url("https://github.com/psf/requests")
        validate_github_url("https://www.github.com/tiangolo/fastapi")

    def test_validate_github_url_rejects_invalid_urls(self) -> None:
        with self.assertRaises(ValueError):
            validate_github_url("http://github.com/psf/requests")
        with self.assertRaises(ValueError):
            validate_github_url("https://gitlab.com/user/repo")
        with self.assertRaises(ValueError):
            validate_github_url("https://github.com/")

    def test_load_repository_files_filters_ignored_dirs_and_extensions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "src").mkdir()
            (root / "src" / "app.py").write_text("print('hi')\n", encoding="utf-8")
            (root / "src" / "index.ts").write_text("export const x = 1;\n", encoding="utf-8")

            # Ignored directory
            (root / "node_modules").mkdir()
            (root / "node_modules" / "pkg.js").write_text("module.exports = {};", encoding="utf-8")

            # Ignored extension
            (root / "uv.lock").write_text("lock content", encoding="utf-8")

            files = load_repository_files(root)
            paths = sorted(f.file_path for f in files)
            self.assertEqual(paths, ["src/app.py", "src/index.ts"])

    def test_load_repository_files_skips_symlinks_escaping_repo(self) -> None:
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as tmp:
            secret = Path(outside) / "id_rsa"
            secret.write_text("PRIVATE KEY MATERIAL\n", encoding="utf-8")

            root = Path(tmp)
            (root / "app.py").write_text("print('hi')\n", encoding="utf-8")
            try:
                (root / "notes.txt").symlink_to(secret)
                (root / "linked_dir").symlink_to(Path(outside), target_is_directory=True)
            except (OSError, NotImplementedError):
                self.skipTest("Symlink creation not permitted on this system (enable Windows Developer Mode)")

            files = load_repository_files(root)
            self.assertEqual([f.file_path for f in files], ["app.py"])
            self.assertFalse(any("PRIVATE KEY" in f.content for f in files))

    def test_is_safe_path_rejects_symlinks_and_escapes(self) -> None:
        """Platform-independent check of the guard (runs even where symlinks can't be created)."""
        with tempfile.TemporaryDirectory() as outside, tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp).resolve()
            inside = root / "app.py"
            inside.write_text("x = 1\n", encoding="utf-8")
            self.assertTrue(is_safe_path(inside, root))

            # A path resolving outside the root is rejected
            escaping = Path(outside) / "id_rsa"
            escaping.write_text("secret", encoding="utf-8")
            self.assertFalse(is_safe_path(escaping, root))

            # Anything reported as a symlink is rejected, even if it points inside
            with patch.object(Path, "is_symlink", return_value=True):
                self.assertFalse(is_safe_path(inside, root))


if __name__ == "__main__":
    unittest.main()

