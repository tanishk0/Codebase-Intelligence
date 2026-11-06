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

    def test_load_repository_files_enforces_max_total_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "a.py").write_text("x = 1\n", encoding="utf-8")
            (root / "b.py").write_text("y = " + ("1" * 100) + "\n", encoding="utf-8")

            files = load_repository_files(root, max_total_bytes=20)
            self.assertEqual([f.file_path for f in files], ["a.py"])


class TestBackgroundReindexJobFlow(unittest.IsolatedAsyncioTestCase):
    @patch("main.SupabaseVectorStore")
    @patch("main.IndexJobStore")
    async def test_reindex_queues_durable_job_and_schedules_worker_claim(
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
        bg.add_task.assert_called_once_with(api_main._claim_and_run_once)

    @patch("main._execute_ingest")
    async def test_run_job_record_sends_heartbeat_and_marks_job_succeeded(
        self, mock_exec: MagicMock
    ) -> None:
        import asyncio

        def slow_ingest(_url: str, _branch: str, _llm: bool) -> dict:
            import time
            time.sleep(0.05)
            return {
                "repo_id": "repo-2",
                "changed_files": 1,
                "unchanged_files": 4,
                "deleted_files": 0,
                "embedded_chunks": 3,
            }

        mock_exec.side_effect = slow_ingest
        job_store = MagicMock()
        job_record = {
            "id": "job-456",
            "repo_id": "repo-2",
            "repo_url": "https://github.com/org/repo2",
            "branch": "dev",
            "llm_summaries": False,
        }

        with patch.object(api_main.settings, "INDEX_JOB_HEARTBEAT_SECONDS", 0.01):
            await api_main._run_job_record(job_record, job_store=job_store)
            await asyncio.sleep(0)

        self.assertGreaterEqual(job_store.heartbeat.call_count, 1)
        job_store.succeed.assert_called_once()
        self.assertEqual(job_store.succeed.call_args.args[0], "job-456")
        self.assertEqual(job_store.succeed.call_args.kwargs["stats"]["changed_files"], 1)


class TestGoogleAuthEndpoints(unittest.TestCase):
    def setUp(self) -> None:
        api_main._TOKEN_CACHE.clear()

    def test_auth_config_returns_google_provider_and_public_key(self) -> None:
        with (
            patch.object(api_main.settings, "SUPABASE_URL", "https://example.supabase.co/"),
            patch.object(api_main.settings, "SUPABASE_KEY", "sb_publishable_test_key"),
            patch.object(api_main.settings, "SUPABASE_ANON_KEY", ""),
        ):
            cfg = api_main.get_auth_config()
            self.assertTrue(cfg["enabled"])
            self.assertEqual(cfg["providers"], ["google"])
            self.assertEqual(cfg["supabase_url"], "https://example.supabase.co")
            self.assertEqual(cfg["supabase_anon_key"], "sb_publishable_test_key")

    def test_google_oauth_url_builds_authorize_endpoint(self) -> None:
        with patch.object(api_main.settings, "SUPABASE_URL", "https://example.supabase.co"):
            res = api_main.get_google_oauth_url(redirect_to="http://localhost:5173")
            self.assertEqual(res["provider"], "google")
            self.assertIn("https://example.supabase.co/auth/v1/authorize?", res["url"])
            self.assertIn("provider=google", res["url"])
            self.assertIn("redirect_to=http%3A%2F%2Flocalhost%3A5173", res["url"])

    @patch("ingestion.vector_store.shared_supabase_client")
    def test_verify_supabase_token_and_auth_context(self, mock_client_fn: MagicMock) -> None:
        fake_user = MagicMock()
        fake_user.id = "user-uuid-1"
        fake_user.email = "dev@example.com"
        fake_user.user_metadata = {"full_name": "Ada Lovelace", "avatar_url": "https://img.example/ada.png"}
        fake_user.app_metadata = {"provider": "google"}
        mock_client_fn.return_value.auth.get_user.return_value = MagicMock(user=fake_user)

        ctx = api_main.get_auth_context(authorization="Bearer valid-jwt-token", x_user_id=None)
        self.assertEqual(ctx.user_id, "user-uuid-1")
        self.assertEqual(ctx.email, "dev@example.com")
        self.assertEqual(ctx.name, "Ada Lovelace")
        self.assertEqual(ctx.avatar_url, "https://img.example/ada.png")

        me = api_main.get_current_user(auth=ctx)
        self.assertTrue(me["authenticated"])
        self.assertEqual(me["user"]["email"], "dev@example.com")

        out = api_main.logout_user(auth=ctx)
        self.assertTrue(out["ok"])
        self.assertNotIn("valid-jwt-token", api_main._TOKEN_CACHE)


if __name__ == "__main__":
    unittest.main()

