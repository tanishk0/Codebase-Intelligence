from pathlib import Path
import sys
import tempfile
import unittest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.git_clone import validate_github_url
from ingestion.loader import load_repository_files


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


if __name__ == "__main__":
    unittest.main()

