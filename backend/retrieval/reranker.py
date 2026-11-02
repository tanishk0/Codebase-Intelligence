from collections import defaultdict
import re
from typing import Any
import httpx
from config import settings
from ingestion.chunker import split_chunk_headers, split_identifier_tokens
from retrieval.query_router import QueryPlan

_WORD_RE = re.compile(r"[a-z0-9]{2,}")
_TEST_FILE_RE = re.compile(r"(^|/)(tests?|__tests__|spec|fixtures?|mocks?)/|(\.|_)test\.|(\.|_)spec\.", re.IGNORECASE)
_strip_chunk_header = split_chunk_header = split_chunk_headers


class RerankerServiceError(RuntimeError):
    """Raised when the cross-encoder reranking service cannot return a usable ranking."""


class NvidiaCrossEncoderReranker:
    """Batched NVIDIA cross-encoder reranker for final ordering of retrieved code chunks."""

    def __init__(
        self,
        api_key: str | None = None,
        endpoint: str | None = None,
        model: str | None = None,
        timeout: float = 30.0,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.NVIDIA_API_KEY
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is missing. Set it in your .env file.")
        self.endpoint = endpoint or settings.NVIDIA_RERANK_URL
        self.model = model or settings.NVIDIA_RERANK_MODEL
        self.timeout = timeout

    @staticmethod
    def _passage(chunk: dict[str, Any]) -> str:
        return "\n".join(
            part for part in (
                f"File: {chunk.get('file_path') or 'unknown'}",
                f"Class: {chunk.get('parent_class')}" if chunk.get("parent_class") else "",
                f"Symbol: {chunk.get('symbol_name')}" if chunk.get("symbol_name") else "",
                str(chunk.get("content") or ""),
            ) if part
        )

    @staticmethod
    def deduplicate(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keeps one copy of each source span before passing all candidates to the model."""
        unique: dict[tuple[str, int, int, str], dict[str, Any]] = {}
        for candidate in candidates:
            key = (
                str(candidate.get("file_path") or ""),
                int(candidate.get("start_line") or 0),
                int(candidate.get("end_line") or 0),
                str(candidate.get("node_type") or ""),
            )
            existing = unique.get(key)
            if existing is None or float(candidate.get("rrf_score") or 0.0) > float(existing.get("rrf_score") or 0.0):
                unique[key] = candidate
        return list(unique.values())

    @staticmethod
    def _results(data: dict[str, Any]) -> list[dict[str, Any]]:
        for key in ("rankings", "results", "data"):
            value = data.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
        raise RerankerServiceError("The AI reranking service returned an unexpected response.")

    def rerank(self, query: str, candidates: list[dict[str, Any]], top_k: int) -> list[dict[str, Any]]:
        if not candidates:
            return []

        payload = {
            "model": self.model,
            "query": {"text": query},
            "passages": [{"text": self._passage(chunk)} for chunk in candidates],
            "truncate": "END",
        }
        headers = {"Authorization": f"Bearer {self.api_key}", "Accept": "application/json"}
        try:
            with httpx.Client(timeout=self.timeout) as client:
                response = client.post(self.endpoint, headers=headers, json=payload)
            if response.status_code >= 400:
                raise RerankerServiceError(f"The AI reranking service returned HTTP {response.status_code}.")
            rankings = self._results(response.json())
        except RerankerServiceError:
            raise
        except (httpx.HTTPError, ValueError, TypeError) as exc:
            raise RerankerServiceError(
                "The AI reranking service is unavailable. Please try again in a moment."
            ) from exc

        scored: list[tuple[float, int]] = []
        for item in rankings:
            index = item.get("index")
            score = item.get("logit", item.get("relevance_score", item.get("score")))
            if not isinstance(index, int) or not (0 <= index < len(candidates)):
                continue
            try:
                scored.append((float(score), index))
            except (TypeError, ValueError):
                continue
        if not scored:
            raise RerankerServiceError("The AI reranking service returned no usable chunk scores.")

        scored.sort(reverse=True)
        ranked: list[dict[str, Any]] = []
        seen: set[int] = set()
        for score, index in scored:
            if index in seen:
                continue
            seen.add(index)
            item = dict(candidates[index])
            item["model_rerank_score"] = score
            ranked.append(item)
            if len(ranked) >= top_k:
                break
        return ranked


def _tokenize(text: str) -> set[str]:
    expanded = f"{text} {split_identifier_tokens(text)}".lower()
    return set(_WORD_RE.findall(expanded))


class CodeReranker:
    """Reranks hybrid (keyword + semantic) candidates with symbol/file boosts and per-file diversity."""

    def __init__(
        self,
        top_k: int | None = None,
        max_chunks_per_file: int | None = None,
    ) -> None:
        self.top_k = top_k or settings.RETRIEVAL_TOP_K
        self.max_chunks_per_file = max_chunks_per_file or settings.RETRIEVAL_MAX_CHUNKS_PER_FILE

    def score_chunk(
        self,
        chunk: dict[str, Any],
        plan: QueryPlan,
        query_tokens: set[str],
        carryover_ids: set[int],
    ) -> float:
        sim = float(chunk.get("similarity") or 0.0)
        fts = min(float(chunk.get("fts_rank") or 0.0), 1.0)
        # Scale RRF score (~0.016 - 0.033) to sit on a comparable [0, 1] scale alongside cosine similarity
        rrf = float(chunk.get("rrf_score") or 0.0) * 15.0
        base = (0.55 * sim + 0.35 * rrf + 0.10 * fts) if (rrf > 0 or fts > 0) else sim

        bonus = 0.0
        file_path = str(chunk.get("file_path") or "")
        symbol_name = str(chunk.get("symbol_name") or "")
        parent_class = str(chunk.get("parent_class") or "")
        node_type = str(chunk.get("node_type") or "")

        # Prefer concrete implementation chunks over file_summary outlines
        if node_type in {"function", "method", "class"}:
            bonus += 0.08
        elif node_type == "file_summary":
            bonus -= 0.04

        # 1. Exact or substring symbol match boost
        if plan.target_symbol:
            target_sym = plan.target_symbol.lower()
            if symbol_name.lower() == target_sym or parent_class.lower() == target_sym:
                bonus += 0.30
            elif target_sym in symbol_name.lower() or target_sym in parent_class.lower():
                bonus += 0.15

        # 2. Target file match boost
        if plan.target_file and plan.target_file.lower() in file_path.lower():
            bonus += 0.25

        # 3. Lexical identifier token overlap
        if query_tokens:
            chunk_tokens = _tokenize(f"{file_path} {parent_class} {symbol_name} {chunk.get('content', '')[:800]}")
            overlap = len(query_tokens & chunk_tokens) / max(len(query_tokens), 1)
            bonus += 0.18 * overlap

        # 4. Carry-over boost for chunks cited in the previous assistant turn
        chunk_id = chunk.get("id")
        if chunk_id is not None and int(chunk_id) in carryover_ids:
            bonus += 0.10

        # 5. Down-rank test files unless the user is asking about tests
        query_mentions_test = any(t in {"test", "tests", "unittest", "pytest", "mock", "smoke"} for t in query_tokens)
        if not query_mentions_test and _TEST_FILE_RE.search(file_path):
            bonus -= 0.12

        return round(base + bonus, 5)

    def rerank(
        self,
        candidates: list[dict[str, Any]],
        plan: QueryPlan,
        carryover_ids: set[int] | None = None,
        top_k: int | None = None,
    ) -> list[dict[str, Any]]:
        """Scores, deduplicates, applies per-file diversity caps, and returns top-K chunks."""
        if not candidates:
            return []

        carry_set = carryover_ids or set()
        result_limit = top_k or self.top_k
        query_tokens = _tokenize(plan.standalone_query)

        # Deduplicate by (file_path, start_line, end_line, node_type) keeping the highest-scored entry
        deduped: dict[tuple[str, int, int, str], dict[str, Any]] = {}
        for item in candidates:
            copy_item = dict(item)
            copy_item["rerank_score"] = self.score_chunk(copy_item, plan, query_tokens, carry_set)
            key = (
                str(copy_item.get("file_path") or ""),
                int(copy_item.get("start_line") or 0),
                int(copy_item.get("end_line") or 0),
                str(copy_item.get("node_type") or ""),
            )
            existing = deduped.get(key)
            if existing is None or copy_item["rerank_score"] > existing["rerank_score"]:
                deduped[key] = copy_item

        ranked = sorted(deduped.values(), key=lambda c: c["rerank_score"], reverse=True)

        # Enforce per-file diversity, file_summary cap, and dynamic drop-off cutoff
        selected: list[dict[str, Any]] = []
        per_file_counts: dict[str, int] = defaultdict(int)
        summary_count = 0
        top_score = ranked[0]["rerank_score"] if ranked else 0.0

        for chunk in ranked:
            if len(selected) >= result_limit:
                break
            # Dynamic cutoff: drop trailing noise if score falls below 35% of top score (after at least 3 results)
            if len(selected) >= 3 and top_score > 0 and chunk["rerank_score"] < top_score * 0.35:
                break

            if chunk.get("node_type") == "file_summary":
                if summary_count >= 2:
                    continue
                summary_count += 1

            fp = str(chunk.get("file_path") or "")
            if per_file_counts[fp] >= self.max_chunks_per_file:
                continue

            per_file_counts[fp] += 1
            selected.append(chunk)

        return selected


class ContextAssembler:
    """Expands top chunks with class headers/preambles, merges overlapping spans, and enforces a token budget."""

    def __init__(self, token_budget: int | None = None) -> None:
        self.token_budget = token_budget or settings.RETRIEVAL_CONTEXT_TOKEN_BUDGET

    @staticmethod
    def merge_adjacent_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Merges overlapping or adjacent chunks within the same file and node_type group."""
        if not chunks:
            return []

        merged: list[dict[str, Any]] = []
        by_source_unit: dict[tuple[str, str, str, str], list[dict[str, Any]]] = defaultdict(list)
        passthrough: list[dict[str, Any]] = []

        for c in chunks:
            if c.get("node_type") in {"file_summary", "class_header", "module_preamble"}:
                passthrough.append(c)
            else:
                # Only chunks from the same source unit may be joined. In particular,
                # adjacent methods and top-level functions must retain their metadata.
                key = (
                    str(c.get("file_path") or ""),
                    str(c.get("node_type") or ""),
                    str(c.get("parent_class") or ""),
                    str(c.get("symbol_name") or ""),
                )
                by_source_unit[key].append(c)

        for (fp, _, _, _), file_chunks in by_source_unit.items():
            ordered = sorted(file_chunks, key=lambda x: (int(x.get("start_line") or 0), int(x.get("end_line") or 0)))
            current = dict(ordered[0])

            for nxt in ordered[1:]:
                cur_start = int(current.get("start_line") or 0)
                cur_end = int(current.get("end_line") or 0)
                nxt_start = int(nxt.get("start_line") or 0)
                nxt_end = int(nxt.get("end_line") or 0)

                # Overlapping or separated by at most 2 lines -> merge into one span
                if nxt_start <= cur_end + 2:
                    if nxt_end > cur_end:
                        headers, cur_body = _strip_chunk_header(str(current.get("content") or ""))
                        _, nxt_body = _strip_chunk_header(str(nxt.get("content") or ""))
                        overlap_lines = max(0, (cur_end - nxt_start) + 1)
                        combined_body = cur_body + nxt_body[overlap_lines:]
                        header_prefix = "\n".join(headers) + "\n" if headers else f"# File: {fp}\n"
                        current["content"] = header_prefix + "\n".join(combined_body)
                        current["end_line"] = nxt_end
                    current["rerank_score"] = max(
                        float(current.get("rerank_score") or 0.0),
                        float(nxt.get("rerank_score") or 0.0),
                    )
                else:
                    merged.append(current)
                    current = dict(nxt)

            merged.append(current)

        all_items = passthrough + merged
        all_items.sort(key=lambda x: float(x.get("rerank_score") or 0.0), reverse=True)
        return all_items

    def assemble(
        self,
        primary_chunks: list[dict[str, Any]],
        neighbor_chunks: list[dict[str, Any]] | None = None,
    ) -> list[dict[str, Any]]:
        """Attaches missing class headers and file preambles, merges overlaps, and trims to token budget."""
        if not primary_chunks:
            return []

        merged_primary = self.merge_adjacent_chunks(primary_chunks)
        seen_keys = {
            (str(c.get("file_path")), int(c.get("start_line") or 0), int(c.get("end_line") or 0))
            for c in merged_primary
        }

        supporting: list[dict[str, Any]] = []
        for nb in neighbor_chunks or []:
            key = (str(nb.get("file_path")), int(nb.get("start_line") or 0), int(nb.get("end_line") or 0))
            if key in seen_keys:
                continue
            seen_keys.add(key)
            nb_copy = dict(nb)
            nb_copy.setdefault("rerank_score", 0.05)
            nb_copy["is_context_expansion"] = True
            supporting.append(nb_copy)

        def _support_priority(item: dict[str, Any]) -> int:
            if item.get("node_type") == "class_header":
                return 0
            if item.get("is_dependency_neighbor") or item.get("node_type") in {"function", "method", "class"}:
                return 1
            return 2

        supporting.sort(key=_support_priority)

        char_budget = self.token_budget * 4
        used_chars = 0
        final_chunks: list[dict[str, Any]] = []

        for chunk in merged_primary + supporting:
            content = str(chunk.get("content") or "")
            # Keep the budget strict. Sending partial code without an explicit user
            # request is more misleading than omitting a chunk that does not fit.
            if used_chars + len(content) > char_budget:
                continue
            final_chunks.append(chunk)
            used_chars += len(content)

        return final_chunks
