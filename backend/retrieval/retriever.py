from dataclasses import dataclass, field
from typing import Any
from config import settings
from ingestion.embedder import NvidiaEmbedder
from ingestion.vector_store import SupabaseVectorStore
from retrieval.llm import NvidiaChatClient
from retrieval.query_router import QueryPlan, QueryRouter
from retrieval.reranker import ContextAssembler, NvidiaCrossEncoderReranker


@dataclass
class RetrievalResult:
    plan: QueryPlan
    chunks: list[dict[str, Any]] = field(default_factory=list)
    repo_summary: str = ""
    no_relevant_code: bool = False

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
                if c.get("is_dependency_neighbor"):
                    tag = f"1-hop dependency {kind}"
                elif c.get("is_context_expansion"):
                    tag = "context header"
                else:
                    tag = kind
                chunk_blocks.append(
                    f"### [{idx}] {fp}:L{start_l}-L{end_l} ({tag})\n```\n{c.get('content', '').strip()}\n```"
                )
            sections.append("## Retrieved Code Context\n" + "\n\n".join(chunk_blocks))
        elif self.no_relevant_code:
            sections.append("## Retrieval Status\nNo relevant indexed code chunks were found for this question.")

        return "\n\n".join(sections)


class CodebaseRetriever:
    """Unified hybrid code retriever: every query runs through keyword + semantic RRF search, reranking, and context expansion."""

    def __init__(
        self,
        vector_store: SupabaseVectorStore,
        embedder: NvidiaEmbedder | None = None,
        llm_client: NvidiaChatClient | None = None,
        router: QueryRouter | None = None,
        model_reranker: NvidiaCrossEncoderReranker | None = None,
        assembler: ContextAssembler | None = None,
        candidate_pool: int | None = None,
    ) -> None:
        self.store = vector_store
        self.embedder = embedder or NvidiaEmbedder()
        self.router = router or QueryRouter(llm_client=llm_client)
        self.model_reranker = model_reranker or NvidiaCrossEncoderReranker()
        self.assembler = assembler or ContextAssembler()
        self.candidate_pool = candidate_pool or settings.RETRIEVAL_CANDIDATE_POOL

    @staticmethod
    def _extract_dependency_symbols(chunks: list[dict[str, Any]], max_primary: int = 3) -> list[str]:
        """Collects 1-hop callees, callers, and base classes from the top primary chunks."""
        primary_symbols = {
            str(c.get("symbol_name") or "")
            for c in chunks
            if c.get("symbol_name") and c.get("node_type") in {"function", "method", "class"}
        }
        ordered: list[str] = []
        seen: set[str] = set()

        for c in chunks[:max_primary]:
            calls_list = [str(x) for x in (c.get("calls") or []) if x]
            called_by_list = [str(x) for x in (c.get("called_by") or []) if x]
            inherits_list = [str(x) for x in (c.get("inherits_from") or []) if x]

            # Fallback: parse `# Calls:`, `# Called by:`, `# Inherits from:` from chunk header lines
            if not (calls_list or called_by_list or inherits_list):
                for line in str(c.get("content") or "").splitlines()[:6]:
                    if not (
                        line.startswith("# Calls:")
                        or line.startswith("# Called by:")
                        or line.startswith("# Inherits from:")
                    ):
                        continue
                    for segment in line.split("|"):
                        seg = segment.strip()
                        if seg.startswith("# Calls:"):
                            calls_list.extend(s.strip() for s in seg[len("# Calls:") :].split(",") if s.strip())
                        elif seg.startswith("# Called by:"):
                            called_by_list.extend(
                                s.strip() for s in seg[len("# Called by:") :].split(",") if s.strip()
                            )
                        elif seg.startswith("# Inherits from:"):
                            inherits_list.extend(
                                s.strip() for s in seg[len("# Inherits from:") :].split(",") if s.strip()
                            )

            # Calls and base classes are stored as bare names, not resolved target identities.
            # Expanding them would frequently attach unrelated symbols, so use only qualified callers.
            raw_edges: list[str] = []
            max_len = max(len(called_by_list), len(inherits_list), len(calls_list), 0)
            for idx in range(max_len):
                if idx < len(called_by_list):
                    raw_edges.append(called_by_list[idx])
                if idx < len(inherits_list):
                    raw_edges.append(inherits_list[idx])
                if idx < len(calls_list):
                    raw_edges.append(calls_list[idx])

            for sym in raw_edges:
                bare = sym.split(".")[-1]
                if not bare or bare in primary_symbols or sym in seen:
                    continue
                seen.add(sym)
                ordered.append(sym)

        return ordered

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

        # 4. Expand context with enclosing class headers, file preambles, and 1-hop dependency neighbors (capped at 4)
        neighbors: list[dict[str, Any]] = []
        if repo_id and top_chunks:
            matched_files = [str(c["file_path"]) for c in top_chunks if c.get("file_path")]
            matched_classes = [
                str(c["parent_class"])
                for c in top_chunks
                if c.get("node_type") == "method" and c.get("parent_class")
            ]
            dep_symbols = self._extract_dependency_symbols(top_chunks, max_primary=3)
            neighbors = self.store.fetch_context_neighbors(
                repo_id=repo_id,
                file_paths=matched_files,
                parent_classes=matched_classes,
                dependency_symbols=dep_symbols,
                max_dependency_chunks=4,
            )

        # 5. Merge overlapping spans and enforce token budget
        assembled = self.assembler.assemble(top_chunks, neighbor_chunks=neighbors)
        return RetrievalResult(plan=plan, chunks=assembled, repo_summary=repo_summary)
