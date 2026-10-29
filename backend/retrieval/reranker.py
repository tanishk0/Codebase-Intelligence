from collections import defaultdict
import re
from typing import Any
from config import settings
from ingestion.chunker import split_identifier_tokens
from retrieval.query_router import QueryPlan

_WORD_RE = re.compile(r"[a-z0-9]{2,}")
_TEST_FILE_RE = re.compile(r"(^|/)(tests?|__tests__|spec|fixtures?|mocks?)/|(\.|_)test\.|(\.|_)spec\.", re.IGNORECASE)


def _tokenize(text: str) -> set[str]:
    expanded = f"{text} {split_identifier_tokens(text)}".lower()
    return set(_WORD_RE.findall(expanded))


def _strip_chunk_header(content: str) -> tuple[list[str], list[str]]:
    """Splits a chunk's content into (# File / # Class header lines, raw code lines)."""
    headers: list[str] = []
    body: list[str] = []
    for line in content.splitlines():
        if not body and (line.startswith("# File:") or line.startswith("# Class:") or line.startswith("# Function:")):
            headers.append(line)
        else:
            body.append(line)
    return headers, body


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
    ) -> list[dict[str, Any]]:
        """Scores, deduplicates, applies per-file diversity caps, and returns top-K chunks."""
        if not candidates:
            return []

        carry_set = carryover_ids or set()
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
            if len(selected) >= self.top_k:
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
        by_file: dict[str, list[dict[str, Any]]] = defaultdict(list)
        passthrough: list[dict[str, Any]] = []

        for c in chunks:
            if c.get("node_type") in {"file_summary", "class_header", "module_preamble"}:
                passthrough.append(c)
            else:
                by_file[str(c.get("file_path") or "")].append(c)

        for fp, file_chunks in by_file.items():
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

        supporting.sort(key=lambda x: 0 if x.get("node_type") == "class_header" else 1)

        char_budget = self.token_budget * 4
        used_chars = 0
        final_chunks: list[dict[str, Any]] = []

        for chunk in merged_primary + supporting:
            content = str(chunk.get("content") or "")
            if used_chars + len(content) > char_budget and final_chunks:
                continue
            final_chunks.append(chunk)
            used_chars += len(content)

        return final_chunks
