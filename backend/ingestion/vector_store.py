from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any
import uuid
from supabase import Client, create_client
from config import settings
from ingestion.chunker import (
    CHUNKER_VERSION,
    HEADER_FORMAT_VERSION,
    SEARCH_TEXT_VERSION,
    CodeChunk,
    TreeSitterChunker,
    build_search_text,
    split_identifier_tokens,
)
from ingestion.dependency import DEPENDENCY_VERSION, DependencyAnalyzer
from ingestion.embedder import EmbeddedChunk, NvidiaEmbedder
from ingestion.loader import LoadedFile, build_file_manifest
from ingestion.summarizer import RepoSummarizer

_BM25_TERM_RE = re.compile(r"[a-z0-9_]{2,}")
# Incremental sync swaps changed files in groups of ~this many embedding batches.
_REPLACE_GROUP_EMBED_BATCHES = 2
_SHARED_CLIENTS: dict[tuple[str, str], Client] = {}


def shared_supabase_client(url: str | None = None, key: str | None = None) -> Client:
    """Returns a cached Supabase client so requests reuse the underlying HTTP connection pool."""
    supabase_url = url if url is not None else settings.SUPABASE_URL
    supabase_key = key if key is not None else settings.SUPABASE_KEY
    if not supabase_url or not supabase_key:
        raise ValueError("SUPABASE_URL and SUPABASE_KEY are required. Set them in your .env file.")
    cache_key = (supabase_url, supabase_key)
    client = _SHARED_CLIENTS.get(cache_key)
    if client is None:
        client = create_client(supabase_url, supabase_key)
        _SHARED_CLIENTS[cache_key] = client
    return client


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
        self.last_sync_stats: dict[str, int] = {}
        self._repo_cache: dict[str, dict[str, Any]] = {}

        if client is not None:
            self.client = client
            return

        self.client = shared_supabase_client(url=url, key=key)

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
        if repo_id in self._repo_cache:
            return dict(self._repo_cache[repo_id])
        res = self.client.table("repositories").select("*").eq("id", repo_id).execute()
        if not res.data:
            return None
        row = dict(res.data[0])
        self._repo_cache[repo_id] = row
        return dict(row)

    def delete_repository(self, repo_id: str) -> bool:
        """Deletes a repository and cascades to its chunks, conversations, messages, and jobs."""
        self._repo_cache.pop(repo_id, None)
        res = self.client.table("repositories").delete().eq("id", repo_id).execute()
        return bool(res.data)

    @staticmethod
    def pipeline_version(embed_model: str, embedding_dim: int) -> str:
        """Fingerprints everything that shapes a stored chunk and its embedding.

        File hashes alone cannot detect a chunker, header-format, or embedding-model change,
        so those edits used to leave the index silently stale. Storing this alongside the
        manifest gates incremental sync on "same pipeline".
        """
        payload = {
            "chunker_version": CHUNKER_VERSION,
            "chunker_params": TreeSitterChunker().pipeline_params(),
            "dependency_version": DEPENDENCY_VERSION,
            "search_text_version": SEARCH_TEXT_VERSION,
            "header_format_version": HEADER_FORMAT_VERSION,
            "embed_model": embed_model,
            "embedding_dim": embedding_dim,
        }
        return hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()[:16]

    @staticmethod
    def _file_edge_signatures(chunks: list[CodeChunk]) -> dict[str, str]:
        """Per-file fingerprint of derived dependency metadata.

        A file's imports/callers come from parsing *every* file, so it can go stale with
        unchanged bytes of its own (another file renames a symbol it calls). Comparing these
        signatures is how an incremental run notices that kind of invalidation.
        """
        edges: dict[str, dict[str, set[str]]] = {}
        for chunk in chunks:
            entry = edges.setdefault(
                chunk.file_path,
                {
                    "imports": set(),
                    "imported_by": set(),
                    "calls": set(),
                    "called_by": set(),
                    "inherits_from": set(),
                },
            )
            entry["imports"].update(chunk.imports)
            entry["imported_by"].update(chunk.imported_by)
            entry["calls"].update(chunk.calls)
            entry["called_by"].update(chunk.called_by)
            entry["inherits_from"].update(chunk.inherits_from)

        return {
            file_path: hashlib.sha256(
                json.dumps({key: sorted(values) for key, values in entry.items()}, sort_keys=True).encode("utf-8")
            ).hexdigest()[:16]
            for file_path, entry in edges.items()
            if entry["imports"] or entry["imported_by"] or entry["calls"] or entry["called_by"] or entry["inherits_from"]
        }

    def _activate_run(
        self,
        repo_id: str,
        run_id: str,
        chunk_count: int,
        embed_model: str,
        embedding_dim: int,
        repo_summary: str = "",
        file_hashes: dict[str, str] | None = None,
        pipeline_version: str = "",
        file_edges: dict[str, str] | None = None,
        expected_run_id: str | None = None,
    ) -> bool:
        """Points the repository at `run_id` with a single-row UPDATE.

        Passing `expected_run_id` makes it a compare-and-swap: the update only applies if the
        repository still points at the run this job diffed against. A slow job can therefore
        never publish an index built on stale input over a newer one.
        """
        payload: dict[str, Any] = {
            "active_run_id": run_id,
            "chunk_count": chunk_count,
            "embed_model": embed_model,
            "embedding_dim": embedding_dim,
            "indexed_at": datetime.now(timezone.utc).isoformat(),
        }
        if repo_summary:
            payload["repo_summary"] = repo_summary
        if file_hashes is not None:
            payload["file_hashes"] = file_hashes
        if pipeline_version:
            payload["pipeline_version"] = pipeline_version
        if file_edges is not None:
            payload["file_edges"] = file_edges

        self._repo_cache.pop(repo_id, None)
        query = self.client.table("repositories").update(payload).eq("id", repo_id)
        if expected_run_id is not None:
            query = query.eq("active_run_id", expected_run_id)
        res = query.execute()
        if expected_run_id is not None:
            return bool(res.data)
        return True

    def _delete_stale_runs(self, repo_id: str, keep_run_id: str) -> None:
        self.client.table("code_chunks").delete().eq("repo_id", repo_id).neq("run_id", keep_run_id).execute()

    def _delete_run(self, repo_id: str, run_id: str) -> None:
        self.client.table("code_chunks").delete().eq("repo_id", repo_id).eq("run_id", run_id).execute()

    # ---------- writes ----------

    @staticmethod
    def _bm25_terms(text: str) -> list[str]:
        """Returns normalized terms, preserving repetitions required by BM25 term frequency."""
        return _BM25_TERM_RE.findall(text.lower())

    def _chunk_row(self, item: EmbeddedChunk) -> dict[str, Any]:
        """Serializes one embedded chunk into a `code_chunks` row (without repo_id/run_id)."""
        search_text = build_search_text(item.chunk)
        return {
            "file_path": item.chunk.file_path,
            "content": item.chunk.content,
            "start_line": item.chunk.start_line,
            "end_line": item.chunk.end_line,
            "node_type": item.chunk.node_type,
            "parent_class": item.chunk.parent_class,
            "symbol_name": item.chunk.symbol_name,
            "imports": item.chunk.imports,
            "imported_by": item.chunk.imported_by,
            "calls": item.chunk.calls,
            "called_by": item.chunk.called_by,
            "inherits_from": item.chunk.inherits_from,
            "search_text": search_text,
            "search_terms": self._bm25_terms(search_text),
            "embedding": item.embedding,
        }

    @staticmethod
    def _check_dimensions(batch: list[EmbeddedChunk], expected: int) -> None:
        for item in batch:
            if len(item.embedding) != expected:
                raise ValueError(
                    f"Embedding dimension mismatch: got {len(item.embedding)}, "
                    f"expected {expected} (check schema vector size)."
                )

    def insert_chunks(self, repo_id: str, run_id: str, embedded_chunks: list[EmbeddedChunk]) -> int:
        """Inserts embedded code chunks for a specific run in batches of `SUPABASE_BATCH_SIZE`."""
        if not embedded_chunks:
            return 0

        rows = [{"repo_id": repo_id, "run_id": run_id, **self._chunk_row(item)} for item in embedded_chunks]
        for start in range(0, len(rows), self.batch_size):
            self.client.table("code_chunks").insert(rows[start : start + self.batch_size]).execute()
        return len(rows)

    def _replace_file_group(
        self,
        repo_id: str,
        run_id: str,
        embedder: NvidiaEmbedder,
        file_paths: list[str],
        chunks: list[CodeChunk],
    ) -> int:
        """Embeds one small group of files, then swaps their rows in a single transaction."""
        rows: list[dict[str, Any]] = []
        if chunks:
            for batch in embedder.iter_embedded_chunks(chunks):
                self._check_dimensions(batch, embedder.dimensions)
                rows.extend(self._chunk_row(item) for item in batch)

        self.client.rpc(
            "replace_file_chunks",
            {
                "p_repo_id": repo_id,
                "p_run_id": run_id,
                "p_file_paths": file_paths,
                "p_rows": rows,
            },
        ).execute()
        return len(rows)

    def _replace_changed_files(
        self,
        repo_id: str,
        run_id: str,
        embedder: NvidiaEmbedder,
        paths_to_replace: list[str],
        chunks_by_file: dict[str, list[CodeChunk]],
    ) -> int:
        """Streams changed/deleted files through `_replace_file_group` in bounded groups.

        Peak RAM is one group (~2 embedding batches) regardless of how large the diff is.
        Each group is atomic, so a reader never sees a file with zero chunks. The manifest is
        written only after every group succeeds, so if the job dies midway the next sync
        re-processes those files, and re-running the swap is idempotent.
        """
        group_limit = max(1, embedder.batch_size * _REPLACE_GROUP_EMBED_BATCHES)
        total = 0
        group_paths: list[str] = []
        group_chunks: list[CodeChunk] = []

        for file_path in paths_to_replace:
            group_paths.append(file_path)
            group_chunks.extend(chunks_by_file.get(file_path, []))
            if len(group_chunks) >= group_limit:
                total += self._replace_file_group(repo_id, run_id, embedder, group_paths, group_chunks)
                group_paths, group_chunks = [], []

        if group_paths:
            total += self._replace_file_group(repo_id, run_id, embedder, group_paths, group_chunks)
        return total

    def index_chunks(
        self,
        repo_url: str,
        chunks: list[CodeChunk],
        embedder: NvidiaEmbedder | None = None,
        branch: str = "main",
        *,
        files: list[LoadedFile] | None = None,
        dependency_analyzer: DependencyAnalyzer | None = None,
        include_summaries: bool = True,
        summarizer: RepoSummarizer | None = None,
        llm_summaries: bool = False,
    ) -> str:
        """Analyzes dependencies and indexes chunks; if `files` and prior `file_hashes` exist, re-embeds only changed files."""
        active_embedder = embedder or NvidiaEmbedder()
        repo_id = self.get_or_create_repository(repo_url=repo_url, branch=branch)
        new_hashes = build_file_manifest(files) if files else None
        pipeline_version = self.pipeline_version(active_embedder.model, active_embedder.dimensions)

        existing_repo = self.get_repository(repo_id) if new_hashes else None
        active_run_id = str((existing_repo or {}).get("active_run_id") or "")
        old_hashes = (existing_repo or {}).get("file_hashes")

        # Incremental reuse is only valid if the existing rows were produced by the same chunker,
        # header format, dependency extractor, and embedding model. Without this check, editing
        # any of those left every file hash unchanged and the index silently stale.
        can_incremental = (
            bool(new_hashes)
            and bool(active_run_id)
            and isinstance(old_hashes, dict)
            and len(old_hashes) > 0
            and (existing_repo or {}).get("embed_model") in {None, active_embedder.model}
            and (existing_repo or {}).get("embedding_dim") in {None, active_embedder.dimensions}
            and (existing_repo or {}).get("pipeline_version") in {None, pipeline_version}
        )

        if can_incremental and new_hashes is not None and isinstance(old_hashes, dict):
            deleted_files = [fp for fp in old_hashes if fp not in new_hashes]
            changed_files = [fp for fp, h in new_hashes.items() if old_hashes.get(fp) != h]
            unchanged_files = [fp for fp, h in new_hashes.items() if old_hashes.get(fp) == h]

            # Fast path: zero files added, modified, or deleted -> zero embedding calls
            if not changed_files and not deleted_files:
                self.last_sync_stats = {
                    "mode": "noop",
                    "changed_files": 0,
                    "unchanged_files": len(unchanged_files),
                    "deleted_files": 0,
                    "embedded_chunks": 0,
                }
                return repo_id

            # Partial update path: at least one file is unchanged, so only re-embed changed files
            if unchanged_files:
                all_chunks = list(chunks)
                analyzer = dependency_analyzer or DependencyAnalyzer()
                if all_chunks:
                    analyzer.analyze(all_chunks, files=files)
                for f in files or []:
                    f.content = ""

                # Imports and callers are derived by parsing every file, so a rename in one file
                # invalidates metadata of files whose own bytes did not change. Signature
                # comparison turns that silently-stale case into a re-chunk of the affected files.
                edge_signatures = self._file_edge_signatures(all_chunks)
                stored_edges = (existing_repo or {}).get("file_edges")
                stored_edges = stored_edges if isinstance(stored_edges, dict) else {}
                edge_changed = [
                    fp
                    for fp in unchanged_files
                    if stored_edges.get(fp) and stored_edges.get(fp) != edge_signatures.get(fp)
                ]

                changed_set = set(changed_files) | set(edge_changed)
                paths_to_replace = sorted(changed_set | set(deleted_files))
                    active_summarizer = summarizer or RepoSummarizer()
                    file_summaries = active_summarizer.build_file_summary_chunks(all_chunks, use_llm=llm_summaries)
                    all_chunks.extend(file_summaries)
                    repo_summary = active_summarizer.build_repo_summary(
                        repo_url=repo_url,
                        file_summary_chunks=file_summaries,
                        use_llm=llm_summaries,
                    )

                chunks_by_file: dict[str, list[CodeChunk]] = defaultdict(list)
                unchanged_chunk_count = 0
                for chunk in all_chunks:
                    if chunk.file_path in changed_set:
                        chunks_by_file[chunk.file_path].append(chunk)
                    else:
                        unchanged_chunk_count += 1

                # Unchanged files' rows are never touched. Changed and deleted files are swapped
                # in bounded, individually atomic groups inside the existing active run.
                embedded_count = self._replace_changed_files(
                    repo_id, active_run_id, active_embedder, paths_to_replace, chunks_by_file
                )

                activated = self._activate_run(
                    repo_id=repo_id,
                    run_id=active_run_id,
                    chunk_count=unchanged_chunk_count + embedded_count,
                    embed_model=active_embedder.model,
                    embedding_dim=active_embedder.dimensions,
                    repo_summary=repo_summary,
                    file_hashes=new_hashes,
                    pipeline_version=pipeline_version,
                    file_edges=edge_signatures,
                    expected_run_id=active_run_id,
                )
                if not activated:
                    raise RuntimeError("The active index changed while this sync was running.")

                self.last_sync_stats = {
                    "mode": "incremental",
                    "changed_files": len(changed_files),
                    "edge_invalidated_files": len(edge_changed),
                    "unchanged_files": len(unchanged_files),
                    "deleted_files": len(deleted_files),
                    "reused_chunks": unchanged_chunk_count,
                    "embedded_chunks": embedded_count,
                }
                return repo_id

        # Full indexing run (first-time index or full rebuild)
        run_id = str(uuid.uuid4())
        all_chunks = list(chunks)
        file_edges: dict[str, str] = {}
        if all_chunks:
            analyzer = dependency_analyzer or DependencyAnalyzer()
            analyzer.analyze(all_chunks, files=files)
            file_edges = self._file_edge_signatures(all_chunks)
        for f in files or []:
            f.content = ""

        repo_summary = ""
        if include_summaries and all_chunks:
            active_summarizer = summarizer or RepoSummarizer()
            file_summaries = active_summarizer.build_file_summary_chunks(all_chunks, use_llm=llm_summaries)
            all_chunks.extend(file_summaries)
            repo_summary = active_summarizer.build_repo_summary(
                repo_url=repo_url,
                file_summary_chunks=file_summaries,
                use_llm=llm_summaries,
            )

        total = 0
        try:
            for embedded_batch in active_embedder.iter_embedded_chunks(all_chunks):
                self._check_dimensions(embedded_batch, active_embedder.dimensions)
                total += self.insert_chunks(repo_id=repo_id, run_id=run_id, embedded_chunks=embedded_batch)

            self._activate_run(
                repo_id=repo_id,
                run_id=run_id,
                chunk_count=total,
                embed_model=active_embedder.model,
                embedding_dim=active_embedder.dimensions,
                repo_summary=repo_summary,
                file_hashes=new_hashes,
                pipeline_version=pipeline_version,
                file_edges=file_edges,
            )
            self.last_sync_stats = {
                "mode": "full",
                "changed_files": len(new_hashes) if new_hashes else 0,
                "unchanged_files": 0,
                "deleted_files": 0,
                "embedded_chunks": total,
            }
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
        """Fetches independent vector and BM25 candidates, then combines their ranks with RRF."""
        expanded_query_text = f"{query_text} {split_identifier_tokens(query_text)}".strip()
        vector_params: dict[str, Any] = {
            "query_embedding": query_embedding,
            "match_repo_id": repo_id,
            "match_count": match_count,
        }
        bm25_params = {
            "query_text": expanded_query_text,
            "match_repo_id": repo_id,
            "match_count": match_count,
        }
        vector_rows = list(self.client.rpc("semantic_search_code_chunks", vector_params).execute().data or [])
        bm25_rows = list(self.client.rpc("bm25_search_code_chunks", bm25_params).execute().data or [])

        fused: dict[int, dict[str, Any]] = {}
        for rank, row in enumerate(vector_rows, start=1):
            item = dict(row)
            item["similarity"] = float(item.get("similarity") or 0.0)
            item["bm25_score"] = 0.0
            item["fts_rank"] = 0.0  # Backward-compatible API field; BM25 is exposed separately.
            item["rrf_score"] = 1.0 / (rrf_k + rank)
            fused[int(item["id"])] = item

        for rank, row in enumerate(bm25_rows, start=1):
            item = fused.get(int(row["id"]))
            if item is None:
                item = dict(row)
                item["similarity"] = 0.0
                item["fts_rank"] = 0.0
                item["rrf_score"] = 0.0
                fused[int(item["id"])] = item
            item["bm25_score"] = float(row.get("bm25_score") or 0.0)
            item["rrf_score"] += 1.0 / (rrf_k + rank)

        return sorted(
            fused.values(),
            key=lambda item: (float(item["rrf_score"]), float(item.get("similarity") or 0.0)),
            reverse=True,
        )[:match_count]

    def fetch_context_neighbors(
        self,
        repo_id: str,
        file_paths: list[str],
        parent_classes: list[str],
        dependency_symbols: list[str] | None = None,
        max_dependency_chunks: int = 4,
        active_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Fetches module_preamble, class_header, and 1-hop dependency neighbor chunks for top hits."""
        if not file_paths and not dependency_symbols:
            return []
        if not active_run_id:
            repo = self.get_repository(repo_id)
            active_run_id = str(repo.get("active_run_id") or "") if repo else ""
        if not active_run_id:
            return []

        cols = "id,repo_id,file_path,content,start_line,end_line,node_type,parent_class,symbol_name"
        neighbors: list[dict[str, Any]] = []

        if file_paths:
            res = (
                self.client.table("code_chunks")
                .select(cols)
                .eq("repo_id", repo_id)
                .eq("run_id", active_run_id)
                .in_("file_path", list(dict.fromkeys(file_paths)))
                .in_("node_type", ["module_preamble", "class_header"])
                .execute()
            )
            rows = list(res.data or [])
            class_set = set(parent_classes)
            neighbors.extend(
                r
                for r in rows
                if r.get("node_type") == "module_preamble"
                or (r.get("node_type") == "class_header" and r.get("parent_class") in class_set)
            )

        if dependency_symbols and max_dependency_chunks > 0:
            # Parse "ClassName.method_name" or bare "symbol_name" while preserving priority order
            ordered_specs: list[tuple[str, str]] = []  # (parent_class_hint, bare_symbol)
            lookup_names: list[str] = []
            for raw_sym in dependency_symbols:
                cleaned = raw_sym.strip()
                if not cleaned:
                    continue
                if "." in cleaned:
                    cls_hint, bare = cleaned.split(".", 1)
                else:
                    cls_hint, bare = "", cleaned
                ordered_specs.append((cls_hint, bare))
                if bare not in lookup_names:
                    lookup_names.append(bare)
                if cls_hint and cls_hint not in lookup_names:
                    lookup_names.append(cls_hint)

            if lookup_names:
                dep_res = (
                    self.client.table("code_chunks")
                    .select(cols)
                    .eq("repo_id", repo_id)
                    .eq("run_id", active_run_id)
                    .in_("symbol_name", lookup_names[:24])
                    .in_("node_type", ["function", "method", "class"])
                    .execute()
                )
                dep_rows = list(dep_res.data or [])
                selected_deps: list[dict[str, Any]] = []
                seen_dep_keys: set[tuple[str, int, int]] = set()

                for cls_hint, bare in ordered_specs:
                    if len(selected_deps) >= max_dependency_chunks:
                        break
                    for row in dep_rows:
                        if len(selected_deps) >= max_dependency_chunks:
                            break
                        row_sym = str(row.get("symbol_name") or "")
                        row_cls = str(row.get("parent_class") or "")
                        matched = (
                            (row_sym == bare and (not cls_hint or row_cls == cls_hint))
                            or (cls_hint and row.get("node_type") == "class" and row_sym == cls_hint)
                        )
                        if not matched:
                            continue
                        key = (
                            str(row.get("file_path") or ""),
                            int(row.get("start_line") or 0),
                            int(row.get("end_line") or 0),
                        )
                        if key in seen_dep_keys:
                            continue
                        seen_dep_keys.add(key)
                        dep_copy = dict(row)
                        dep_copy["is_dependency_neighbor"] = True
                        selected_deps.append(dep_copy)

                neighbors.extend(selected_deps)

        return neighbors

    def fetch_chunks_by_ids(
        self,
        repo_id: str,
        chunk_ids: list[int],
        active_run_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Re-fetches carry-over chunks only from the repository's currently active index run."""
        if not chunk_ids:
            return []
        if not active_run_id:
            repo = self.get_repository(repo_id)
            active_run_id = str(repo.get("active_run_id") or "") if repo else ""
        if not active_run_id:
            return []
        cols = "id,repo_id,file_path,content,start_line,end_line,node_type,parent_class,symbol_name"
        res = (
            self.client.table("code_chunks")
            .select(cols)
            .eq("repo_id", repo_id)
            .eq("run_id", active_run_id)
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

    def list_conversations(self, repo_id: str, limit: int = 50) -> list[dict[str, Any]]:
        res = (
            self.client.table("conversations")
            .select("id,repo_id,title,created_at,updated_at")
            .eq("repo_id", repo_id)
            .order("updated_at", desc=True)
            .limit(limit)
            .execute()
        )
        return list(res.data or [])

    def get_conversation_messages(
        self,
        conversation_id: str,
        limit: int = 10,
        before_id: int | None = None,
    ) -> tuple[list[dict[str, Any]], bool]:
        """Returns an oldest-first page, with an opaque numeric cursor represented by message id."""
        query = (
            self.client.table("messages")
            .select("*")
            .eq("conversation_id", conversation_id)
            .order("id", desc=True)
            .limit(limit + 1)
        )
        if before_id is not None:
            query = query.lt("id", before_id)
        res = query.execute()
        rows = list(res.data or [])
        has_more = len(rows) > limit
        rows = rows[:limit]
        rows.reverse()
        return rows, has_more

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

    def set_conversation_title(self, conversation_id: str, title: str) -> None:
        self.client.table("conversations").update(
            {"title": title[:120], "updated_at": datetime.now(timezone.utc).isoformat()}
        ).eq("id", conversation_id).execute()
