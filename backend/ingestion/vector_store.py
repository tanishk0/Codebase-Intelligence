import base64
from datetime import datetime, timezone
import json
from typing import Any
import uuid
from supabase import Client, create_client
from config import settings
from ingestion.chunker import CodeChunk
from ingestion.embedder import EmbeddedChunk, NvidiaEmbedder


def assert_server_key(key: str) -> None:
    """Refuse public/anon keys. The backend must use the secret (service_role) key.

    Publishable/anon keys are meant to be shipped to browsers. With RLS enabled (as our schema does)
    they cannot read or write these tables; with RLS disabled they would let anyone dump or wipe the index.
    """
    if key.startswith("sb_publishable_"):
        raise ValueError(
            "SUPABASE_KEY is a publishable (public) key. Use the secret key (sb_secret_...) from "
            "Supabase Dashboard -> Project Settings -> API Keys. Never expose it to the frontend."
        )

    # Legacy JWT-style keys: inspect the role claim without verifying the signature
    parts = key.split(".")
    if len(parts) == 3:
        try:
            padded = parts[1] + "=" * (-len(parts[1]) % 4)
            role = json.loads(base64.urlsafe_b64decode(padded)).get("role")
        except (ValueError, json.JSONDecodeError):
            return
        if role == "anon":
            raise ValueError(
                "SUPABASE_KEY is the legacy anon key. Use the service_role / secret key for the backend."
            )


class SupabaseVectorStore:
    """Manages repository metadata, vector storage, and similarity search in Supabase (pgvector).

    Re-indexing is crash-safe: chunks are written under a fresh run_id, and only after every batch
    succeeds is repositories.active_run_id flipped to it (single-row update). Search only serves the
    active run, so a failed re-index leaves the previous index fully intact.
    """

    def __init__(
        self,
        url: str | None = None,
        key: str | None = None,
        batch_size: int | None = None,
        client: Client | None = None,
    ) -> None:
        self.batch_size = batch_size or settings.SUPABASE_BATCH_SIZE

        if client is not None:
            self.client = client
            return

        supabase_url = url if url is not None else settings.SUPABASE_URL
        supabase_key = key if key is not None else settings.SUPABASE_KEY
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY are required. Set them in your .env file.")
        assert_server_key(supabase_key)

        self.client = create_client(supabase_url, supabase_key)

    # ---------- repository bookkeeping ----------

    def get_or_create_repository(self, repo_url: str, branch: str = "main") -> str:
        """Returns the repository id, creating the record if needed. Does not touch the active index."""
        clean_url = repo_url.strip().rstrip("/")
        res = (
            self.client.table("repositories")
            .upsert({"repo_url": clean_url, "branch": branch}, on_conflict="repo_url")
            .execute()
        )
        if not res.data:
            raise RuntimeError(f"Failed to upsert repository record for {clean_url}")
        return res.data[0]["id"]

    def _activate_run(self, repo_id: str, run_id: str, chunk_count: int, embed_model: str, embedding_dim: int) -> None:
        """Atomically switches search to the new run (single-row UPDATE)."""
        self.client.table("repositories").update(
            {
                "active_run_id": run_id,
                "chunk_count": chunk_count,
                "embed_model": embed_model,
                "embedding_dim": embedding_dim,
                "indexed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", repo_id).execute()

    def _delete_stale_runs(self, repo_id: str, keep_run_id: str) -> None:
        self.client.table("code_chunks").delete().eq("repo_id", repo_id).neq("run_id", keep_run_id).execute()

    def _delete_run(self, repo_id: str, run_id: str) -> None:
        self.client.table("code_chunks").delete().eq("repo_id", repo_id).eq("run_id", run_id).execute()

    # ---------- writes ----------

    def insert_chunks(self, repo_id: str, run_id: str, embedded_chunks: list[EmbeddedChunk]) -> int:
        """Inserts embedded code chunks for a specific run in batches."""
        if not embedded_chunks:
            return 0

        rows = [
            {
                "repo_id": repo_id,
                "run_id": run_id,
                "file_path": item.chunk.file_path,
                "content": item.chunk.content,
                "start_line": item.chunk.start_line,
                "end_line": item.chunk.end_line,
                "node_type": item.chunk.node_type,
                "parent_class": item.chunk.parent_class,
                "embedding": item.embedding,
            }
            for item in embedded_chunks
        ]

        inserted = 0
        for start in range(0, len(rows), self.batch_size):
            batch = rows[start : start + self.batch_size]
            self.client.table("code_chunks").insert(batch).execute()
            inserted += len(batch)
        return inserted

    def index_chunks(
        self,
        repo_url: str,
        chunks: list[CodeChunk],
        embedder: NvidiaEmbedder | None = None,
        branch: str = "main",
    ) -> str:
        """Embeds chunks and stores them under a new run, then atomically activates that run.

        Embeddings are streamed batch-by-batch into Supabase, so memory stays flat for large repos.
        On any failure the partial run is cleaned up and the previous index keeps serving search.
        """
        active_embedder = embedder or NvidiaEmbedder()
        repo_id = self.get_or_create_repository(repo_url=repo_url, branch=branch)
        run_id = str(uuid.uuid4())

        total = 0
        try:
            for embedded_batch in active_embedder.iter_embedded_chunks(chunks):
                for item in embedded_batch:
                    if len(item.embedding) != active_embedder.dimensions:
                        raise ValueError(
                            f"Embedding dimension mismatch: got {len(item.embedding)}, "
                            f"expected {active_embedder.dimensions} (check schema vector size)."
                        )
                total += self.insert_chunks(repo_id=repo_id, run_id=run_id, embedded_chunks=embedded_batch)

            self._activate_run(
                repo_id=repo_id,
                run_id=run_id,
                chunk_count=total,
                embed_model=active_embedder.model,
                embedding_dim=active_embedder.dimensions,
            )
        except BaseException:
            # Best-effort cleanup of the partial run; the old active run is untouched either way.
            try:
                self._delete_run(repo_id, run_id)
            except Exception:
                pass
            raise

        # Old runs are invisible to search already; deleting them just reclaims space.
        try:
            self._delete_stale_runs(repo_id, keep_run_id=run_id)
        except Exception:
            pass

        return repo_id

    # ---------- reads ----------

    def search(
        self,
        query_embedding: list[float],
        repo_id: str | None = None,
        match_count: int = 10,
        similarity_threshold: float = 0.2,
    ) -> list[dict[str, Any]]:
        """Calls the match_code_chunks Postgres RPC function for cosine similarity retrieval."""
        params: dict[str, Any] = {
            "query_embedding": query_embedding,
            "match_repo_id": repo_id,
            "match_count": match_count,
            "similarity_threshold": similarity_threshold,
        }
        res = self.client.rpc("match_code_chunks", params).execute()
        return list(res.data or [])

    def query(
        self,
        query_text: str,
        repo_id: str | None = None,
        embedder: NvidiaEmbedder | None = None,
        match_count: int = 10,
        similarity_threshold: float = 0.2,
    ) -> list[dict[str, Any]]:
        """Embeds a natural language or code query and retrieves matching code chunks."""
        active_embedder = embedder or NvidiaEmbedder()
        query_vector = active_embedder.embed_query(query_text)
        return self.search(
            query_embedding=query_vector,
            repo_id=repo_id,
            match_count=match_count,
            similarity_threshold=similarity_threshold,
        )
