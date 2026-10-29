from datetime import datetime, timezone
from typing import Any
import uuid
from supabase import Client, create_client
from config import settings
from ingestion.chunker import CodeChunk, build_search_text, split_identifier_tokens
from ingestion.embedder import EmbeddedChunk, NvidiaEmbedder
from ingestion.summarizer import RepoSummarizer


class SupabaseVectorStore:
    """Manages repository metadata, vector storage, unified hybrid search, and chat persistence in Supabase."""

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

        self.client = create_client(supabase_url, supabase_key)

    # ---------- repository bookkeeping ----------

    def list_repositories(self) -> list[dict[str, Any]]:
        """Lists all indexed repositories ordered by most recently indexed."""
        res = (
            self.client.table("repositories")
            .select("id,repo_url,branch,chunk_count,embed_model,embedding_dim,indexed_at,active_run_id")
            .order("indexed_at", desc=True)
            .execute()
        )
        return list(res.data or [])

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

    def get_repository(self, repo_id: str) -> dict[str, Any] | None:
        """Fetches repository metadata including active_run_id and repo_summary."""
        res = self.client.table("repositories").select("*").eq("id", repo_id).execute()
        return res.data[0] if res.data else None

    def _activate_run(
        self,
        repo_id: str,
        run_id: str,
        chunk_count: int,
        embed_model: str,
        embedding_dim: int,
        repo_summary: str = "",
    ) -> None:
        """Atomically switches search to the new run (single-row UPDATE)."""
        payload: dict[str, Any] = {
            "active_run_id": run_id,
            "chunk_count": chunk_count,
            "embed_model": embed_model,
            "embedding_dim": embedding_dim,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        if repo_summary:
            payload["repo_summary"] = repo_summary
        self.client.table("repositories").update(payload).eq("id", repo_id).execute()

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
                "symbol_name": item.chunk.symbol_name,
                "search_text": build_search_text(item.chunk),
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
        *,
        include_summaries: bool = True,
        summarizer: RepoSummarizer | None = None,
        llm_summaries: bool = False,
    ) -> str:
        """Embeds chunks (plus optional file/repo summaries), stores them under a new run, and activates it."""
        active_embedder = embedder or NvidiaEmbedder()
        repo_id = self.get_or_create_repository(repo_url=repo_url, branch=branch)
        run_id = str(uuid.uuid4())

        all_chunks = list(chunks)
        repo_summary = ""
        if include_summaries and chunks:
            active_summarizer = summarizer or RepoSummarizer()
            file_summaries = active_summarizer.build_file_summary_chunks(chunks, use_llm=llm_summaries)
            all_chunks.extend(file_summaries)
            repo_summary = active_summarizer.build_repo_summary(
                repo_url=repo_url,
                file_summary_chunks=file_summaries,
                use_llm=llm_summaries,
            )

        total = 0
        try:
            for embedded_batch in active_embedder.iter_embedded_chunks(all_chunks):
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
                repo_summary=repo_summary,
            )
        except BaseException:
            try:
                self._delete_run(repo_id, run_id)
            except Exception:
                pass
            raise

        try:
            self._delete_stale_runs(repo_id, keep_run_id=run_id)
        except Exception:
            pass

        return repo_id

    # ---------- unified hybrid search ----------

    def hybrid_search(
        self,
        query_embedding: list[float],
        query_text: str,
        repo_id: str | None = None,
        match_count: int = 30,
        rrf_k: int = 60,
    ) -> list[dict[str, Any]]:
        """Executes unified hybrid search (pgvector semantic similarity + full-text keyword search via RRF)."""
        expanded_query_text = f"{query_text} {split_identifier_tokens(query_text)}".strip()
        params: dict[str, Any] = {
            "query_embedding": query_embedding,
            "query_text": expanded_query_text,
            "match_repo_id": repo_id,
            "match_count": match_count,
            "rrf_k": rrf_k,
        }
        res = self.client.rpc("hybrid_search_code_chunks", params).execute()
        return list(res.data or [])

    def fetch_context_neighbors(
        self,
        repo_id: str,
        file_paths: list[str],
        parent_classes: list[str],
    ) -> list[dict[str, Any]]:
        """Fetches module_preamble and class_header chunks for the given files/classes to expand context."""
        if not file_paths:
            return []
        repo = self.get_repository(repo_id)
        active_run_id = repo.get("active_run_id") if repo else None
        if not active_run_id:
            return []

        cols = "id,repo_id,file_path,content,start_line,end_line,node_type,parent_class,symbol_name"
        res = (
            self.client.table("code_chunks")
            .select(cols)
            .eq("repo_id", repo_id)
            .eq("run_id", active_run_id)
            .in_("file_path", list(set(file_paths)))
            .in_("node_type", ["module_preamble", "class_header"])
            .execute()
        )
        rows = list(res.data or [])
        class_set = set(parent_classes)
        return [
            r
            for r in rows
            if r.get("node_type") == "module_preamble"
            or (r.get("node_type") == "class_header" and r.get("parent_class") in class_set)
        ]

    def fetch_chunks_by_ids(self, chunk_ids: list[int]) -> list[dict[str, Any]]:
        """Re-fetches specific chunks by primary key (used to carry over cited chunks across chat turns)."""
        if not chunk_ids:
            return []
        cols = "id,repo_id,file_path,content,start_line,end_line,node_type,parent_class,symbol_name"
        res = (
            self.client.table("code_chunks")
            .select(cols)
            .in_("id", list(dict.fromkeys(chunk_ids)))
            .execute()
        )
        return list(res.data or [])

    def query(
        self,
        query_text: str,
        repo_id: str | None = None,
        embedder: NvidiaEmbedder | None = None,
        match_count: int = 10,
    ) -> list[dict[str, Any]]:
        """Embeds a query and retrieves matching code chunks using unified hybrid search (keyword + semantic)."""
        active_embedder = embedder or NvidiaEmbedder()
        query_vector = active_embedder.embed_query(query_text)
        return self.hybrid_search(
            query_embedding=query_vector,
            query_text=query_text,
            repo_id=repo_id,
            match_count=match_count,
        )

    # ---------- conversation & message persistence ----------

    def create_conversation(self, repo_id: str | None = None, title: str = "") -> str:
        res = (
            self.client.table("conversations")
            .insert({"repo_id": repo_id, "title": title})
            .execute()
        )
        if not res.data:
            raise RuntimeError("Failed to create conversation record")
        return res.data[0]["id"]

    def get_conversation(self, conversation_id: str) -> dict[str, Any] | None:
        res = self.client.table("conversations").select("*").eq("id", conversation_id).execute()
        return res.data[0] if res.data else None

    def get_conversation_messages(self, conversation_id: str, limit: int = 10) -> list[dict[str, Any]]:
        res = (
            self.client.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        rows = list(res.data or [])
        rows.reverse()
        return rows

    def save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
        standalone_query: str = "",
        cited_chunk_ids: list[int] | None = None,
    ) -> dict[str, Any]:
        payload = {
            "conversation_id": conversation_id,
            "role": role,
            "content": content,
            "standalone_query": standalone_query,
            "cited_chunk_ids": cited_chunk_ids or [],
        }
        res = self.client.table("messages").insert(payload).execute()
        return res.data[0] if res.data else payload

    def update_rolling_summary(self, conversation_id: str, rolling_summary: str) -> None:
        self.client.table("conversations").update(
            {
                "rolling_summary": rolling_summary,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", conversation_id).execute()
