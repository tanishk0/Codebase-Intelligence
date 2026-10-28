from dataclasses import dataclass, field
from typing import Any
from ingestion.vector_store import SupabaseVectorStore
from retrieval.llm import NvidiaChatClient
from retrieval.query_router import QueryPlan
from retrieval.retriever import CodebaseRetriever, RetrievalResult

SYSTEM_PROMPT = """You are Codebase Copilot, an expert software engineering assistant answering questions about a repository.
Ground your answers strictly in the provided repository overview and retrieved code chunks.
- Always cite file paths and line ranges in the format `[file_path:Lstart-Lend]` when referencing code.
- If the retrieved chunks do not contain enough information to be certain, state clearly what is visible and what is missing.
- Keep explanations concise, accurate, and directly tied to the actual code symbols."""


@dataclass
class ChatTurnResponse:
    answer: str
    plan: QueryPlan
    retrieval: RetrievalResult
    conversation_id: str | None = None
    cited_chunk_ids: list[int] = field(default_factory=list)


class ConversationalRAGEngine:
    """Multi-turn conversational RAG engine with follow-up condensing, chunk carry-over, and rolling memory."""

    def __init__(
        self,
        retriever: CodebaseRetriever,
        llm_client: NvidiaChatClient | None = None,
        vector_store: SupabaseVectorStore | None = None,
        max_recent_messages: int = 6,
    ) -> None:
        self.retriever = retriever
        self.llm = llm_client or NvidiaChatClient()
        self.store = vector_store or retriever.store
        self.max_recent_messages = max_recent_messages

    def ask(
        self,
        user_message: str,
        repo_id: str | None = None,
        *,
        conversation_id: str | None = None,
        history: list[dict[str, Any]] | None = None,
    ) -> ChatTurnResponse:
        """Answers a user question (or follow-up) with automatic query rewriting and context carry-over."""
        rolling_summary = ""
        active_history: list[dict[str, Any]] = list(history or [])

        # 1. Load conversation state from Supabase if a conversation_id was provided
        if conversation_id and not active_history:
            conv = self.store.get_conversation(conversation_id)
            if conv:
                rolling_summary = str(conv.get("rolling_summary") or "")
                repo_id = repo_id or conv.get("repo_id")
            active_history = self.store.get_conversation_messages(
                conversation_id, limit=self.max_recent_messages + 4
            )

        # 2. Extract cited chunk IDs from the most recent assistant message for follow-up carry-over
        carryover_ids: list[int] = []
        for msg in reversed(active_history):
            if msg.get("role") == "assistant" and msg.get("cited_chunk_ids"):
                carryover_ids = [int(x) for x in msg["cited_chunk_ids"]]
                break

        # 3. Condense follow-up, route, hybrid-search, rerank, and expand context
        recent_window = active_history[-self.max_recent_messages :]
        retrieval = self.retriever.retrieve(
            user_message=user_message,
            repo_id=repo_id,
            history=recent_window,
            rolling_summary=rolling_summary,
            carryover_chunk_ids=carryover_ids,
        )

        # 4. Build prompt with rolling summary, recent chat turns, and cited code context
        messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
        if rolling_summary:
            messages.append(
                {"role": "system", "content": f"Summary of earlier conversation:\n{rolling_summary}"}
            )

        for turn in recent_window:
            role = turn.get("role", "user")
            if role in {"user", "assistant"}:
                messages.append({"role": role, "content": str(turn.get("content") or "")})

        context_block = retrieval.format_context_for_llm()
        if context_block:
            user_prompt = f"{context_block}\n\n---\nUser Question: {user_message}"
        else:
            user_prompt = user_message
        messages.append({"role": "user", "content": user_prompt})

        # 5. Generate answer with the main Nemotron model (550B Ultra by default)
        answer = self.llm.complete(messages, use_fast_model=False, temperature=0.1, max_tokens=1200)
        cited_ids = retrieval.cited_chunk_ids

        # 6. Persist turn & update rolling summary if conversation_id is active
        if conversation_id:
            self.store.save_message(
                conversation_id=conversation_id,
                role="user",
                content=user_message,
                standalone_query=retrieval.plan.standalone_query,
            )
            self.store.save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=answer,
                cited_chunk_ids=cited_ids,
            )
            if len(active_history) >= self.max_recent_messages:
                self._refresh_rolling_summary(conversation_id, rolling_summary, recent_window[:2])

        return ChatTurnResponse(
            answer=answer,
            plan=retrieval.plan,
            retrieval=retrieval,
            conversation_id=conversation_id,
            cited_chunk_ids=cited_ids,
        )

    def _refresh_rolling_summary(
        self,
        conversation_id: str,
        previous_summary: str,
        evicted_turns: list[dict[str, Any]],
    ) -> None:
        if not evicted_turns:
            return
        turns_text = "\n".join(f"{t.get('role')}: {t.get('content', '')[:400]}" for t in evicted_turns)
        prompt = [
            {
                "role": "system",
                "content": (
                    "Update the running conversation summary in 2-4 concise sentences, "
                    "preserving exact file paths, class names, and function names discussed."
                ),
            },
            {
                "role": "user",
                "content": f"Previous summary:\n{previous_summary}\n\nNew turns to fold in:\n{turns_text}",
            },
        ]
        try:
            updated = self.llm.complete(prompt, use_fast_model=True, max_tokens=200)
            if updated:
                self.store.update_rolling_summary(conversation_id, updated)
        except Exception:
            pass

