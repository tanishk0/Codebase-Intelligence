from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi.testclient import TestClient
import main
from ingestion.vector_store import SupabaseVectorStore


class TestWorkspaceAuthorization(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(main.app)
        self.addCleanup(self.client.close)
        main._TOKEN_CACHE.clear()

    def test_all_workspace_routes_reject_missing_or_invalid_tokens(self):
        routes = [
            ("GET", "/api/repos", None),
            ("DELETE", "/api/repos/repo-1", None),
            ("GET", "/api/repos/repo-1/conversations", None),
            ("POST", "/api/repos/repo-1/conversations", {"title": "New chat"}),
            ("GET", "/api/conversations/conv-1/messages", None),
            ("POST", "/api/ingest", {"repo_url": "local"}),
            ("POST", "/api/repos/repo-1/reindex", None),
            ("POST", "/api/repos/repo-1/sync", None),
            ("GET", "/api/jobs/job-1", None),
            ("GET", "/api/repos/repo-1/jobs", None),
            ("POST", "/api/chat", {"message": "Explain", "repo_id": "repo-1"}),
            ("POST", "/api/chat/stream", {"message": "Explain", "repo_id": "repo-1"}),
        ]
        with patch("main._verify_supabase_token", return_value=None), patch("main.SupabaseVectorStore") as store:
            for headers in ({}, {"X-User-Id": "victim"}, {"Authorization": "Bearer invalid", "X-User-Id": "victim"}):
                for method, url, body in routes:
                    with self.subTest(method=method, url=url, headers=headers):
                        response = self.client.request(method, url, json=body, headers=headers)
                        self.assertEqual(response.status_code, 401, response.text)
            store.assert_not_called()

    @patch("main._verify_supabase_token", return_value={"id": "user-1"})
    @patch("main.IndexJobStore")
    @patch("main.SupabaseVectorStore")
    def test_other_users_and_ownerless_repositories_are_inaccessible(self, store_cls, jobs_cls, _verify):
        store = store_cls.return_value
        store.get_conversation.return_value = {"id": "conv-1", "repo_id": "repo-1"}
        jobs_cls.return_value.get.return_value = {"id": "job-1", "repo_id": "repo-1"}
        headers = {"Authorization": "Bearer valid", "X-User-Id": "user-2"}
        routes = [
            ("DELETE", "/api/repos/repo-1", None),
            ("GET", "/api/repos/repo-1/conversations", None),
            ("POST", "/api/repos/repo-1/conversations", {}),
            ("GET", "/api/conversations/conv-1/messages", None),
            ("POST", "/api/repos/repo-1/reindex", None),
            ("POST", "/api/repos/repo-1/sync", None),
            ("GET", "/api/jobs/job-1", None),
            ("GET", "/api/repos/repo-1/jobs", None),
            ("POST", "/api/chat", {"message": "Explain", "repo_id": "repo-1"}),
            ("POST", "/api/chat/stream", {"message": "Explain", "conversation_id": "conv-1"}),
        ]
        with patch("main.NvidiaEmbedder") as embedder:
            for owner in ("user-2", None):
                store.get_repository.return_value = {"id": "repo-1", "owner_id": owner}
                for method, url, body in routes:
                    with self.subTest(owner=owner, url=url):
                        response = self.client.request(method, url, json=body, headers=headers)
                        self.assertEqual(response.status_code, 404, response.text)
            embedder.assert_not_called()
        store.delete_repository.assert_not_called()
        store.create_conversation.assert_not_called()
        store.get_conversation_messages.assert_not_called()
        jobs_cls.return_value.enqueue.assert_not_called()

    @patch("main._verify_supabase_token", return_value={"id": "user-1"})
    @patch("main.SupabaseVectorStore")
    def test_repository_list_is_scoped_to_verified_user(self, store_cls, _verify):
        store_cls.return_value.list_repositories.return_value = []
        response = self.client.get("/api/repos", headers={"Authorization": "Bearer valid", "X-User-Id": "other"})
        self.assertEqual(response.status_code, 200)
        store_cls.return_value.list_repositories.assert_called_once_with(owner_id="user-1")

    def test_chat_cannot_mix_repository_and_conversation(self):
        store = MagicMock()
        store.get_conversation.return_value = {"repo_id": "repo-1"}
        store.get_repository.return_value = {"owner_id": "user-1"}
        with self.assertRaises(main.HTTPException) as error:
            main.authorize_chat(store, main.ChatRequest(message="Explain", repo_id="repo-2", conversation_id="conv-1"), main.AuthContext(user_id="user-1"))
        self.assertEqual(error.exception.status_code, 400)

    @patch("main._verify_supabase_token", return_value={"id": "user-1"})
    @patch("main._execute_ingest", return_value={"repo_id": "repo-1"})
    def test_ingestion_uses_verified_owner(self, ingest, _verify):
        response = self.client.post("/api/ingest", json={"repo_url": "local"}, headers={"Authorization": "Bearer valid", "X-User-Id": "other"})
        self.assertEqual(response.status_code, 200, response.text)
        ingest.assert_called_once_with("local", None, False, "user-1")


    def test_service_key_is_never_used_as_public_auth_configuration(self):
        for key in ("sb_secret_test", "eyJhbGciOi.service_role.signature"):
            with patch.object(main.settings, "SUPABASE_URL", "https://example.supabase.co"), patch.object(main.settings, "SUPABASE_ANON_KEY", ""), patch.object(main.settings, "SUPABASE_KEY", key):
                config = main.get_auth_config()
                self.assertEqual(config["supabase_anon_key"], "")
                self.assertFalse(config["enabled"])

    def test_repository_upsert_and_listing_include_owner(self):
        client = MagicMock()
        table = client.table.return_value
        table.upsert.return_value.execute.return_value.data = [{"id": "repo-1"}]
        store = SupabaseVectorStore(client=client)
        self.assertEqual(store.get_or_create_repository("https://github.com/org/repo", owner_id="user-1"), "repo-1")
        self.assertEqual(table.upsert.call_args.args[0]["owner_id"], "user-1")
        self.assertEqual(table.upsert.call_args.kwargs["on_conflict"], "owner_id,repo_url")
        store.list_repositories(owner_id="user-1")
        table.select.return_value.order.return_value.eq.assert_called_once_with("owner_id", "user-1")
