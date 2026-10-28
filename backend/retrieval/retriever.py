from dataclasses import dataclass, field
from typing import Any
from config import settings
from ingestion.embedder import NvidiaEmbedder
from ingestion.vector_store import SupabaseVectorStore
from retrieval.llm import NvidiaChatClient
from retrieval.query_router import QueryPlan, QueryRouter
from retrieval.reranker import CodeReranker, ContextAssembler


@dataclass
class RetrievalResult:
    plan: QueryPlan
    chunks: list[dict[str, Any]] = field(default_factory=list)
    repo_summary: str = ""

    @property
    def cited_chunk_ids(self) -> list[int]:
        return [
            int(c["id"])
            for c in self.chunks
            if c.get("id") is not None and not c.get("is_context_expansion")
        ]

    def format_context_for_llm(self) -> str:
        """Formats the retrieved chunks and repository summary into a cited prompt block."""
        sections: list[str] = []
        if self.repo_summary:
            sections.append(f"## Repository Overview\n{self.repo_summary}")

        if self.chunks:
            chunk_blocks: list[str] = []
            for idx, c in enumerate(self.chunks, start=1):
                fp = c.get("file_path", "unknown")
                start_l = c.get("start_line", 1)
                end_l = c.get("end_line", start_l)
                kind = c.get("node_type", "code")
                tag = "context header" if c.get("is_context_expansion") else kind
                chunk_blocks.append(
                    f"### [{idx}] {fp}:L{start_l}-L{end_l} ({tag})\n```\n{c.get('content', '').strip()}\n```"
                )
            sections.append("## Retrieved Code Context\n" + "\n\n".join(chunk_blocks))

        return "\n\n".join(sections)


class CodebaseRetriever:
    """Unified hybrid code retriever: every query runs through keyword + semantic RRF search, reranking, and context expansion."""

    def __init__(
        self,
        vector_store: SupabaseVectorStore,
        embedder: NvidiaEmbedder | None = None,
        llm_client: NvidiaChatClient | None = None,
        router: QueryRouter | None = None,
        reranker: CodeReranker | None = None,
        assembler: ContextAssembler | None = None,
        candidate_pool: int | None = None,
    ) -> None:
        self.store = vector_store
        self.embedder = embedder or NvidiaEmbedder()
        self.router = router or QueryRouter(llm_client=llm_client)
        self.reranker = reranker or CodeReranker()
        self.assembler = assembler or ContextAssembler()
        self.candidate_pool = candidate_pool or settings.RETRIEVAL_CANDIDATE_POOL

    def retrieve(
        self,
        user_message: str,
        repo_id: str | None = None,
        *,
        history: list[dict[str, Any]] | None = None,
        rolling_summary: str = "",
        carryover_chunk_ids: list[int] | None = None,
    ) -> RetrievalResult:
        plan = self.router.plan(user_message, history=history, rolling_summary=rolling_summary)

        repo_meta = self.store.get_repository(repo_id) if repo_id else None
        repo_summary = str((repo_meta or {}).get("repo_summary") or "")

        if not plan.needs_retrieval:
            return RetrievalResult(plan=plan, chunks=[], repo_summary=repo_summary)

        # 1. Unified hybrid search (keyword + semantic RRF) for every query
        query_embedding = self.embedder.embed_query(plan.standalone_query)
        candidates = self.store.hybrid_search(
            query_embedding=query_embedding,
            query_text=plan.standalone_query,
            repo_id=repo_id,
            match_count=self.candidate_pool,
        )

        # 2. Carry over chunks cited in the previous turn so follow-ups stay grounded
        carry_set = set(carryover_chunk_ids or [])
        if carry_set:
            for item in self.store.fetch_chunks_by_ids(list(carry_set)):
                item.setdefault("similarity", 0.45)
                candidates.append(item)

        # 3. Rerank and apply per-file diversity caps
        top_chunks = self.reranker.rerank(candidates, plan=plan, carryover_ids=carry_set)

        # 4. Expand context with enclosing class headers and file preambles
        neighbors: list[dict[str, Any]] = []
        if repo_id and top_chunks:
            matched_files = [str(c["file_path"]) for c in top_chunks if c.get("file_path")]
            matched_classes = [
                str(c["parent_class"])
                for c in top_chunks
                if c.get("node_type") == "method" and c.get("parent_class")
            ]
            neighbors = self.store.fetch_context_neighbors(
                repo_id=repo_id,
                file_paths=matched_files,
                parent_classes=matched_classes,
            )

        # 5. Merge overlapping spans and enforce token budget
        assembled = self.assembler.assemble(top_chunks, neighbor_chunks=neighbors)
        return RetrievalResult(plan=plan, chunks=assembled, repo_summary=repo_summary)
