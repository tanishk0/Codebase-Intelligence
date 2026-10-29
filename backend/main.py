from pathlib import Path
from typing import Any
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from config import BACKEND_DIR, ROOT_DIR, settings
from ingestion.chunker import TreeSitterChunker
from ingestion.embedder import NvidiaEmbedder
from ingestion.git_clone import RepoCloner
from ingestion.loader import load_repository_files
from ingestion.summarizer import RepoSummarizer
from ingestion.vector_store import SupabaseVectorStore
from retrieval.chat_engine import ConversationalRAGEngine
from retrieval.llm import NvidiaChatClient
from retrieval.retriever import CodebaseRetriever

FRONTEND_DIR = ROOT_DIR / "frontend"

app = FastAPI(title="Codebase Copilot API", version="0.2.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class IngestRequest(BaseModel):
    repo_url: str
    branch: str | None = None
    llm_summaries: bool = False


class ChatRequest(BaseModel):
    message: str
    repo_id: str | None = None
    conversation_id: str | None = None
    history: list[dict[str, Any]] | None = None


@app.get("/api/health")
def health_check() -> dict[str, Any]:
    """Checks environment credentials and Supabase table readiness for the UI banner."""
    issues: list[str] = []
    if not settings.NVIDIA_API_KEY:
        issues.append("NVIDIA_API_KEY is missing in .env")
    if not settings.SUPABASE_URL or not settings.SUPABASE_KEY:
        issues.append("SUPABASE_URL or SUPABASE_KEY is missing in .env")

    db_ready = False
    if not issues:
        try:
            store = SupabaseVectorStore()
            store.list_repositories()
            db_ready = True
        except Exception as exc:
            issues.append(
                f"Supabase tables not created yet ({exc}). Copy and run backend/supabase_schema.sql in your Supabase Dashboard -> SQL Editor."
            )

    return {
        "ok": len(issues) == 0 and db_ready,
        "db_ready": db_ready,
        "embed_model": settings.NVIDIA_EMBED_MODEL,
        "chat_model": settings.NVIDIA_CHAT_MODEL,
        "fast_model": settings.NVIDIA_FAST_MODEL,
        "issues": issues,
    }


@app.get("/api/repos")
def list_repos() -> dict[str, Any]:
    try:
        store = SupabaseVectorStore()
        return {"repos": store.list_repositories()}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ingest")
def ingest_repository(req: IngestRequest) -> dict[str, Any]:
    raw_url = req.repo_url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Repository URL is required.")

    try:
        store = SupabaseVectorStore()
        embedder = NvidiaEmbedder()
        llm_client = NvidiaChatClient() if req.llm_summaries else None
        summarizer = RepoSummarizer(llm_client=llm_client)
        chunker = TreeSitterChunker()

        # Shortcut: allow typing "local" to index this local backend workspace in seconds without git clone
        if raw_url.lower() == "local":
            files = load_repository_files(BACKEND_DIR)
            chunks = chunker.chunk_all(files)
            repo_url_key = "https://github.com/local/codebase-copilot"
            branch_label = req.branch or "main"
        else:
            cloner = RepoCloner(raw_url, branch=req.branch or None)
            try:
                repo_dir = cloner.clone()
                files = load_repository_files(repo_dir)
                chunks = chunker.chunk_all(files)
                repo_url_key = raw_url.rstrip("/")
                branch_label = req.branch or "default"
            finally:
                cloner.cleanup()

        if not chunks:
            raise HTTPException(status_code=400, detail="No indexable source files found in repository.")

        repo_id = store.index_chunks(
            repo_url=repo_url_key,
            chunks=chunks,
            embedder=embedder,
            branch=branch_label,
            include_summaries=True,
            summarizer=summarizer,
            llm_summaries=req.llm_summaries,
        )
        repo_meta = store.get_repository(repo_id) or {}
        return {
            "repo_id": repo_id,
            "repo_url": repo_url_key,
            "file_count": len(files),
            "ast_chunk_count": len(chunks),
            "total_indexed_chunks": repo_meta.get("chunk_count", len(chunks)),
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat")
def chat_with_repo(req: ChatRequest) -> dict[str, Any]:
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

    try:
        store = SupabaseVectorStore()
        embedder = NvidiaEmbedder()
        llm = NvidiaChatClient()
        retriever = CodebaseRetriever(vector_store=store, embedder=embedder, llm_client=llm)
        engine = ConversationalRAGEngine(retriever=retriever, llm_client=llm, vector_store=store)

        conv_id = req.conversation_id
        if not conv_id and req.repo_id:
            try:
                conv_id = store.create_conversation(repo_id=req.repo_id, title=req.message[:80])
            except Exception:
                conv_id = None

        turn = engine.ask(
            user_message=req.message,
            repo_id=req.repo_id,
            conversation_id=conv_id,
            history=req.history,
        )

        formatted_chunks = [
            {
                "id": c.get("id"),
                "file_path": c.get("file_path"),
                "start_line": c.get("start_line"),
                "end_line": c.get("end_line"),
                "node_type": c.get("node_type"),
                "parent_class": c.get("parent_class", ""),
                "symbol_name": c.get("symbol_name", ""),
                "similarity": round(float(c.get("similarity") or 0.0), 4),
                "rrf_score": round(float(c.get("rrf_score") or 0.0), 4),
                "fts_rank": round(float(c.get("fts_rank") or 0.0), 4),
                "rerank_score": round(float(c.get("rerank_score") or 0.0), 4),
                "is_context_expansion": bool(c.get("is_context_expansion", False)),
                "content": c.get("content", ""),
            }
            for c in turn.retrieval.chunks
        ]

        return {
            "answer": turn.answer,
            "original_query": turn.plan.original_query,
            "standalone_query": turn.plan.standalone_query,
            "needs_retrieval": turn.plan.needs_retrieval,
            "target_symbol": turn.plan.target_symbol,
            "target_file": turn.plan.target_file,
            "conversation_id": turn.conversation_id,
            "cited_chunk_ids": turn.cited_chunk_ids,
            "chunks": formatted_chunks,
        }
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))


def main() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
