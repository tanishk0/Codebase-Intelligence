from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.git_clone import RepoCloner, validate_github_url
from ingestion.loader import is_safe_path, load_repository_files
import main as api_main


class TestIngestionHelpers(unittest.TestCase):
    def test_repo_cloner_normalizes_default_branch_to_none(self) -> None:
        self.assertIsNone(RepoCloner("https://github.com/psf/requests", branch="default").branch)
        self.assertIsNone(RepoCloner("https://github.com/psf/requests", branch="").branch)
        self.assertEqual(RepoCloner("https://github.com/psf/requests", branch="dev").branch, "dev")
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


class TestBackgroundReindexJobFlow(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        api_main._MEMORY_JOBS.clear()

    @patch("main.SupabaseVectorStore")
    @patch("main.IndexJobStore")
    async def test_reindex_queues_durable_job_when_db_available(
        self, mock_job_store_cls: MagicMock, mock_store_cls: MagicMock
    ) -> None:
        mock_store_cls.return_value.get_repository.return_value = {
            "id": "repo-1",
            "repo_url": "https://github.com/org/repo",
            "branch": "main",
        }
        mock_job_store_cls.return_value.enqueue.return_value = {
            "id": "job-123",
            "repo_id": "repo-1",
            "kind": "incremental",
            "status": "queued",
            "repo_url": "https://github.com/org/repo",
            "branch": "main",
            "attempt": 0,
            "stats": {},
            "error": "",
        }
        bg = MagicMock()
        result = await api_main.reindex_repository("repo-1", background_tasks=bg, wait=False)

        self.assertEqual(result["job_id"], "job-123")
        self.assertEqual(result["status"], "queued")
        bg.add_task.assert_not_called()

    @patch("main._execute_ingest")
    @patch("main.SupabaseVectorStore")
    @patch("main.IndexJobStore", side_effect=RuntimeError("table missing"))
    async def test_reindex_falls_back_to_memory_job_and_executes_in_bg(
        self, _mock_job_store: MagicMock, mock_store_cls: MagicMock, mock_exec: MagicMock
    ) -> None:
        mock_store_cls.return_value.get_repository.return_value = {
            "id": "repo-2",
            "repo_url": "https://github.com/org/repo2",
            "branch": "dev",
        }
        mock_exec.return_value = {
            "repo_id": "repo-2",
            "changed_files": 1,
            "unchanged_files": 4,
            "deleted_files": 0,
            "embedded_chunks": 3,
        }
        bg = MagicMock()
        result = await api_main.reindex_repository("repo-2", background_tasks=bg, wait=False)

        job_id = result["job_id"]
        self.assertEqual(result["status"], "queued")
        self.assertEqual(bg.add_task.call_count, 1)

        # Simulate FastAPI running the scheduled background task
        fn, job_record, store_arg = bg.add_task.call_args.args
        await fn(job_record, store_arg)

        polled = api_main.get_index_job(job_id)["job"]
        self.assertEqual(polled["status"], "succeeded")
        self.assertEqual(polled["stats"]["changed_files"], 1)
        self.assertEqual(polled["stats"]["embedded_chunks"], 3)


if __name__ == "__main__":
    unittest.main()

