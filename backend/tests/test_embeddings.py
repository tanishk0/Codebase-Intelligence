import base64
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

import httpx

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from ingestion.chunker import CodeChunk
from ingestion.embedder import EmbeddedChunk, EmbeddingError, NvidiaEmbedder, RateLimiter, parse_retry_after
from ingestion.vector_store import SupabaseVectorStore, assert_server_key


def make_response(status: int, data: list | None = None, headers: dict | None = None) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.headers = headers or {}
    resp.text = "error body"
    resp.json.return_value = {"data": data or []}
    return resp


def make_embedder(**overrides) -> tuple[NvidiaEmbedder, list[float]]:
    """Embedder with no real sleeping and no rate limiting; returns it plus a list recording sleeps."""
    sleeps: list[float] = []
    kwargs = dict(
        api_key="nvapi-test-key",
        base_url="https://integrate.api.nvidia.com/v1",
        model="test-model",
        dimensions=2,
        batch_size=2,
        requests_per_minute=0,
        max_retries=3,
        sleep=sleeps.append,
    )
    kwargs.update(overrides)
    return NvidiaEmbedder(**kwargs), sleeps


class TestNvidiaEmbedder(unittest.TestCase):
    @patch("ingestion.embedder.httpx.Client")
    def test_embed_chunks_batches_and_preserves_order(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.post.side_effect = [
            make_response(200, [{"index": 1, "embedding": [0.2, 0.2]}, {"index": 0, "embedding": [0.1, 0.1]}]),
            make_response(200, [{"index": 0, "embedding": [0.3, 0.3]}]),
        ]
        embedder, _ = make_embedder()
        chunks = [CodeChunk(f"{n}.py", f"def {n}(): pass", 1, 1, "function") for n in "abc"]

        embedded = embedder.embed_chunks(chunks)

        self.assertEqual([e.embedding for e in embedded], [[0.1, 0.1], [0.2, 0.2], [0.3, 0.3]])
        self.assertEqual([e.chunk.file_path for e in embedded], ["a.py", "b.py", "c.py"])
        payload = client.post.call_args_list[0].kwargs["json"]
        self.assertEqual(payload["input_type"], "passage")
        self.assertEqual(payload["dimensions"], 2)

    @patch("ingestion.embedder.httpx.Client")
    def test_embed_query_uses_query_input_type(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.post.return_value = make_response(200, [{"index": 0, "embedding": [0.9, 0.8]}])
        embedder, _ = make_embedder()

        self.assertEqual(embedder.embed_query("where is auth?"), [0.9, 0.8])
        self.assertEqual(client.post.call_args.kwargs["json"]["input_type"], "query")

    @patch("ingestion.embedder.httpx.Client")
    def test_permanent_errors_fail_fast_without_retry(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        for status in (400, 401, 410):
            client.post.reset_mock()
            client.post.return_value = make_response(status)
            embedder, sleeps = make_embedder()
            with self.assertRaises(EmbeddingError):
                embedder.embed_texts(["x"])
            self.assertEqual(client.post.call_count, 1, f"status {status} should not be retried")
            self.assertEqual(sleeps, [])

    @patch("ingestion.embedder.httpx.Client")
    def test_429_retries_honouring_retry_after(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.post.side_effect = [
            make_response(429, headers={"Retry-After": "7"}),
            make_response(503),
            make_response(200, [{"index": 0, "embedding": [1.0, 0.0]}]),
        ]
        embedder, sleeps = make_embedder()

        self.assertEqual(embedder.embed_texts(["x"]), [[1.0, 0.0]])
        self.assertEqual(client.post.call_count, 3)
        self.assertEqual(sleeps, [7.0, 4])  # Retry-After honoured, then exponential backoff (2**2)

    @patch("ingestion.embedder.httpx.Client")
    def test_retries_exhausted_raises(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.post.return_value = make_response(429)
        embedder, _ = make_embedder(max_retries=2)
        with self.assertRaises(EmbeddingError):
            embedder.embed_texts(["x"])
        self.assertEqual(client.post.call_count, 3)

    @patch("ingestion.embedder.httpx.Client")
    def test_transport_errors_are_retried(self, mock_client_cls: MagicMock) -> None:
        client = mock_client_cls.return_value.__enter__.return_value
        client.post.side_effect = [
            httpx.ConnectTimeout("timeout"),
            make_response(200, [{"index": 0, "embedding": [0.5, 0.5]}]),
        ]
        embedder, _ = make_embedder()
        self.assertEqual(embedder.embed_texts(["x"]), [[0.5, 0.5]])

    def test_parse_retry_after(self) -> None:
        self.assertEqual(parse_retry_after("12"), 12.0)
        self.assertIsNone(parse_retry_after(None))
        self.assertIsNone(parse_retry_after("garbage"))
        # A past HTTP date must not crash and clamps to 0
        self.assertEqual(parse_retry_after("Wed, 21 Oct 2015 07:28:00 GMT"), 0.0)

    def test_rate_limiter_spaces_requests(self) -> None:
        now = [100.0]
        sleeps: list[float] = []

        def fake_sleep(s: float) -> None:
            sleeps.append(s)
            now[0] += s

        limiter = RateLimiter(requests_per_minute=30, clock=lambda: now[0], sleep=fake_sleep)
        limiter.wait()  # first call: immediate
        limiter.wait()  # must wait 2s (60/30)
        now[0] += 5.0
        limiter.wait()  # enough time passed: immediate
        self.assertEqual(sleeps, [2.0])


def _jwt_with_role(role: str) -> str:
    payload = base64.urlsafe_b64encode(json.dumps({"role": role}).encode()).decode().rstrip("=")
    return f"header.{payload}.signature"


class TestServerKeyGuard(unittest.TestCase):
    def test_rejects_publishable_and_anon_keys(self) -> None:
        with self.assertRaises(ValueError):
            assert_server_key("sb_publishable_abc123")
        with self.assertRaises(ValueError):
            assert_server_key(_jwt_with_role("anon"))

    def test_accepts_secret_and_service_role_keys(self) -> None:
        assert_server_key("sb_secret_abc123")
        assert_server_key(_jwt_with_role("service_role"))


class TestSupabaseVectorStore(unittest.TestCase):
    def setUp(self) -> None:
        self.client = MagicMock()
        self.repo_table = MagicMock()
        self.chunks_table = MagicMock()
        self.client.table.side_effect = lambda name: self.repo_table if name == "repositories" else self.chunks_table
        self.repo_table.upsert.return_value.execute.return_value.data = [{"id": "repo-1"}]
        self.store = SupabaseVectorStore(batch_size=2, client=self.client)

    def _embedder_yielding(self, batches: list[list[EmbeddedChunk]] | Exception, dims: int = 2) -> MagicMock:
        embedder = MagicMock()
        embedder.model = "test-model"
        embedder.dimensions = dims

        def gen(_chunks):
            if isinstance(batches, Exception):
                raise batches
            for b in batches:
                if isinstance(b, Exception):
                    raise b
                yield b

        embedder.iter_embedded_chunks.side_effect = gen
        return embedder

    @staticmethod
    def _ec(name: str) -> EmbeddedChunk:
        return EmbeddedChunk(CodeChunk(name, "code", 1, 2, "function"), [0.1, 0.2])

    def test_index_chunks_activates_run_then_cleans_stale_runs(self) -> None:
        embedder = self._embedder_yielding([[self._ec("a.py"), self._ec("b.py")], [self._ec("c.py")]])

        repo_id = self.store.index_chunks("https://github.com/org/repo/", chunks=[], embedder=embedder)

        self.assertEqual(repo_id, "repo-1")
        # Repo upsert must NOT touch active_run_id (old index keeps serving during re-index)
        upsert_payload = self.repo_table.upsert.call_args.args[0]
        self.assertNotIn("active_run_id", upsert_payload)
        self.assertEqual(upsert_payload["repo_url"], "https://github.com/org/repo")

        # All inserted rows share one run_id
        inserted_rows = [row for call in self.chunks_table.insert.call_args_list for row in call.args[0]]
        self.assertEqual(len(inserted_rows), 3)
        run_ids = {row["run_id"] for row in inserted_rows}
        self.assertEqual(len(run_ids), 1)
        run_id = run_ids.pop()

        # Activation flips the pointer to that run with metadata
        update_payload = self.repo_table.update.call_args.args[0]
        self.assertEqual(update_payload["active_run_id"], run_id)
        self.assertEqual(update_payload["chunk_count"], 3)
        self.assertEqual(update_payload["embed_model"], "test-model")

        # Stale runs deleted afterwards (repo_id match, run_id != new run)
        delete_chain = self.chunks_table.delete.return_value.eq.return_value
        delete_chain.neq.assert_called_once_with("run_id", run_id)

    def test_failed_index_cleans_partial_run_and_never_activates(self) -> None:
        embedder = self._embedder_yielding([[self._ec("a.py")], EmbeddingError("rate limited")])

        with self.assertRaises(EmbeddingError):
            self.store.index_chunks("https://github.com/org/repo", chunks=[], embedder=embedder)

        self.repo_table.update.assert_not_called()
        run_id = self.chunks_table.insert.call_args.args[0][0]["run_id"]
        # Partial run removed: delete().eq(repo_id).eq(run_id)
        self.chunks_table.delete.return_value.eq.return_value.eq.assert_called_once_with("run_id", run_id)
        self.chunks_table.delete.return_value.eq.return_value.neq.assert_not_called()

    def test_dimension_mismatch_aborts(self) -> None:
        embedder = self._embedder_yielding([[self._ec("a.py")]], dims=1024)
        with self.assertRaises(ValueError):
            self.store.index_chunks("https://github.com/org/repo", chunks=[], embedder=embedder)
        self.repo_table.update.assert_not_called()

    def test_search_rpc(self) -> None:
        self.client.rpc.return_value.execute.return_value.data = [{"file_path": "a.py", "similarity": 0.88}]
        results = self.store.search([0.1, 0.2], repo_id="repo-1", match_count=5, similarity_threshold=0.3)
        self.assertEqual(len(results), 1)
        self.client.rpc.assert_called_once_with(
            "match_code_chunks",
            {"query_embedding": [0.1, 0.2], "match_repo_id": "repo-1", "match_count": 5, "similarity_threshold": 0.3},
        )


if __name__ == "__main__":
    unittest.main()
