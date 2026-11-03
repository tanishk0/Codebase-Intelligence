from dataclasses import dataclass
import re
from typing import Any
from retrieval.llm import NvidiaChatClient

_BACKTICK_SYMBOL_RE = re.compile(r"`([A-Za-z_][A-Za-z0-9_.]*)`")
_FILE_PATH_RE = re.compile(
    r"\b([A-Za-z0-9_.\-/]+\.(?:py|ts|tsx|js|jsx|mjs|cjs|json|ya?ml|toml|md|sql))\b"
)
_CAMEL_OR_SNAKE_IDENT_RE = re.compile(
    r"\b([A-Z][a-z0-9]+(?:[A-Z][a-z0-9]+)+|[a-z]+(?:_[a-z0-9]+)+)\b"
)
_NO_RETRIEVAL_PATTERNS = re.compile(
    r"^(?:summarize that|shorten that|in bullet points|explain (?:that|it) (?:more )?simply|"
    r"translate that|give me a shorter version|make it concise|eli5)\b",
    re.IGNORECASE,
)
_CHITCHAT_PATTERNS = re.compile(
    r"^(?:"
    r"(?:hi|hello|hey|greetings|howdy|sup|yo|good\s+(?:morning|afternoon|evening|day))|"
    r"(?:thanks|thank\s+you|thx|ty|cheers)|"
    r"(?:ok|okay|k|cool|great|awesome|perfect|nice|sounds\s+good|got\s+it|understood|all\s+good)|"
    r"(?:ok\s+(?:thanks|thank\s+you|got\s+it|cool|great))|"
    r"(?:who\s+are\s+you|what\s+(?:can\s+you\s+do|are\s+you)|help(?:\s+me)?)|"
    r"(?:bye|goodbye|see\s+ya)"
    r")[!.,? ]*$",
    re.IGNORECASE,
)
_FOLLOWUP_REFERENCE_RE = re.compile(
    r"\b(it|its|that|this|those|these|they|them|the above|previous|last|other method|same class|same file)\b"
    r"|^(?:why|what about|how about|and |also |where does|when does)\b",
    re.IGNORECASE,
)


@dataclass
class QueryPlan:
    original_query: str
    standalone_query: str
    needs_retrieval: bool = True
    target_symbol: str | None = None
    target_file: str | None = None


class QueryRewriteError(RuntimeError):
    """Raised when a conversational follow-up cannot be rewritten safely."""


def extract_query_hints(query: str) -> tuple[str | None, str | None]:
    """Deterministically extracts soft file path and symbol hints from a query string for reranking."""
    file_match = _FILE_PATH_RE.search(query)
    target_file = file_match.group(1) if file_match else None

    target_symbol: str | None = None
    for bt_match in _BACKTICK_SYMBOL_RE.finditer(query):
        candidate = bt_match.group(1)
        if not _FILE_PATH_RE.fullmatch(candidate):
            target_symbol = candidate.split(".")[-1]
            break

    if target_symbol is None:
        ident_match = _CAMEL_OR_SNAKE_IDENT_RE.search(query)
        if ident_match:
            target_symbol = ident_match.group(1)

    return target_file, target_symbol


class QueryRouter:
    """Condenses conversational follow-up questions and prepares queries for unified hybrid search."""

    def __init__(self, llm_client: NvidiaChatClient | None = None) -> None:
        self.llm = llm_client

    def plan(
        self,
        user_message: str,
        history: list[dict[str, Any]] | None = None,
        rolling_summary: str = "",
    ) -> QueryPlan:
        clean_msg = user_message.strip()
        if not clean_msg:
            raise ValueError("User message cannot be empty.")

        has_history = bool(history)
        target_file, target_symbol = extract_query_hints(clean_msg)

        # 1. Greetings, pleasantries, acknowledgments, and meta-queries -> skip retrieval
        if not target_file and not target_symbol and _CHITCHAT_PATTERNS.match(clean_msg):
            return QueryPlan(
                original_query=clean_msg,
                standalone_query=clean_msg,
                needs_retrieval=False,
            )

        # 2. Pure formatting/meta follow-up on previous assistant answer -> skip retrieval
        if has_history and _NO_RETRIEVAL_PATTERNS.search(clean_msg):
            return QueryPlan(
                original_query=clean_msg,
                standalone_query=clean_msg,
                needs_retrieval=False,
            )

        standalone = clean_msg
        needs_retrieval = True

        # 3. If there is conversation history and the message looks like a follow-up, condense it
        if has_history and self._needs_condensing(clean_msg):
            standalone, needs_retrieval = self._condense_with_history(
                clean_msg, history or [], rolling_summary
            )

        # 4. Extract optional symbol/file hints (used as soft reranking signals)
        if not target_file and not target_symbol:
            target_file, target_symbol = extract_query_hints(standalone)

        # Safety override: if the query explicitly targets a file or symbol, always retrieve code
        if target_file or target_symbol:
            needs_retrieval = True

        return QueryPlan(
            original_query=clean_msg,
            standalone_query=standalone,
            needs_retrieval=needs_retrieval,
            target_symbol=target_symbol,
            target_file=target_file,
        )

    def _needs_condensing(self, message: str) -> bool:
        return bool(_FOLLOWUP_REFERENCE_RE.search(message))

    def _condense_with_history(
        self,
        user_message: str,
        history: list[dict[str, Any]],
        rolling_summary: str,
    ) -> tuple[str, bool]:
        """Rewrites a follow-up question into a self-contained codebase search query."""
        if self.llm is None:
            last_text = " ".join(m.get("content", "") for m in history[-2:])
            last_file, last_symbol = extract_query_hints(last_text)
            suffix = " ".join(x for x in (last_symbol, last_file) if x)
            return (f"{user_message} ({suffix})".strip() if suffix else user_message), True

        recent_turns = "\n".join(
            f"{m.get('role', 'user').upper()}: {m.get('content', '')[:500]}"
            for m in history[-6:]
        )
        summary_prefix = f"Earlier summary: {rolling_summary}\n\n" if rolling_summary else ""
        messages = [
            {
                "role": "system",
                "content": (
                    "You rewrite follow-up questions in a codebase Q&A chat into a standalone search query.\n"
                    "- Resolve pronouns ('it', 'that', 'this method', 'the class') using the conversation history.\n"
                    "- Preserve exact function names, class names, and file paths.\n"
                    "- Do NOT return placeholders, empty strings, or ellipses like '...'. Write the actual complete search query.\n"
                    "- Set \"needs_retrieval\": false ONLY if the user is just asking to reformat/shorten the previous answer.\n"
                    "Return ONLY JSON: {\"needs_retrieval\": true, \"standalone_query\": \"actual search question\"}"
                ),
            },
            {
                "role": "user",
                "content": f"{summary_prefix}Recent turns:\n{recent_turns}\n\nFollow-up question: {user_message}",
            },
        ]
        try:
            data = self.llm.complete_json(messages, use_fast_model=True, max_tokens=200)
            needs_retrieval = bool(data.get("needs_retrieval", True))
            raw_rewritten = str(data.get("standalone_query") or "").strip()
            if not raw_rewritten or raw_rewritten.strip(". ") == "" or raw_rewritten.lower() in {"...", "none", "null"}:
                rewritten = user_message
            else:
                rewritten = raw_rewritten

            user_file, user_sym = extract_query_hints(user_message)
            if user_file and user_file.lower() not in rewritten.lower():
                rewritten = f"{rewritten} {user_file}"
            if user_sym and user_sym.lower() not in rewritten.lower():
                rewritten = f"{rewritten} {user_sym}"

            return rewritten.strip(), needs_retrieval
        except Exception as exc:
            raise QueryRewriteError(
                "I couldn't resolve this follow-up because the AI service is unavailable. "
                "Please try again in a moment or ask a self-contained question."
            ) from exc
