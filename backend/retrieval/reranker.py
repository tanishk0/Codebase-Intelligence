from collections import defaultdict
import time
from typing import Any, Callable
import httpx
from config import settings
from ingestion.chunker import split_chunk_headers
from ingestion.embedder import MAX_BACKOFF_SECONDS, RateLimiter, parse_retry_after, shared_rate_limiter


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
        requests_per_minute: int | None = None,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.NVIDIA_API_KEY
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is missing. Set it in your .env file.")
        self.endpoint = endpoint or settings.NVIDIA_RERANK_URL
        self.model = model or settings.NVIDIA_RERANK_MODEL
        self.timeout = timeout
        self.max_retries = max_retries
        self._sleep = sleep
        rpm = requests_per_minute if requests_per_minute is not None else settings.NVIDIA_REQUESTS_PER_MINUTE
        if rate_limiter is not None:
            self.rate_limiter = rate_limiter
        elif api_key is None and requests_per_minute is None and sleep is time.sleep:
            self.rate_limiter = shared_rate_limiter("nvidia_nim", rpm)
        else:
            self.rate_limiter = RateLimiter(requests_per_minute or 0, sleep=sleep)

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
                response: httpx.Response | None = None
                for attempt in range(self.max_retries + 1):
                    is_last = attempt == self.max_retries
                    self.rate_limiter.wait("interactive")
                    response = client.post(self.endpoint, headers=headers, json=payload)
                    if response.status_code == 429 and not is_last:
                        retry_after = parse_retry_after(response.headers.get("Retry-After")) if hasattr(response, "headers") else None
                        delay = retry_after if retry_after is not None else min(2 ** (attempt + 1), MAX_BACKOFF_SECONDS)
                        self._sleep(delay)
                        continue
                    break
            if response is None or response.status_code >= 400:
                code = response.status_code if response is not None else 503
                raise RerankerServiceError(f"The AI reranking service returned HTTP {code}.")
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
            item["rerank_score"] = score
            item["model_rerank_score"] = score
            ranked.append(item)
            if len(ranked) >= top_k:
                break
        return ranked


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
                        headers, cur_body = split_chunk_headers(str(current.get("content") or ""))
                        _, nxt_body = split_chunk_headers(str(nxt.get("content") or ""))
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
