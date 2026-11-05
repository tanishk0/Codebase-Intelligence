import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any, Iterator
import uuid
from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

from config import BACKEND_DIR, ROOT_DIR, settings
from ingestion.chunker import TreeSitterChunker
from ingestion.embedder import NvidiaEmbedder
from ingestion.git_clone import RepoCloner
from ingestion.jobs import IndexJobStore, public_job
from ingestion.loader import build_file_manifest, load_repository_files
from ingestion.summarizer import RepoSummarizer
from ingestion.vector_store import SupabaseVectorStore
from retrieval.chat_engine import ConversationalRAGEngine
from retrieval.llm import NvidiaChatClient
from retrieval.query_router import QueryRewriteError
from retrieval.reranker import RerankerServiceError
from retrieval.retriever import CodebaseRetriever

FRONTEND_DIR = ROOT_DIR / "frontend"
LOCAL_REPO_URL = "https://github.com/local/codebase-copilot"
_SYNC_LOCKS: dict[str, asyncio.Lock] = {}
_WORKER_ID = f"worker-{uuid.uuid4().hex[:8]}"


def _execute_ingest(raw_url: str, branch: str | None = None, llm_summaries: bool = False) -> dict[str, Any]:
    """Loads files with SHA-256 hashes, chunks ASTs, and runs full or incremental indexing."""
    store = SupabaseVectorStore()
    embedder = NvidiaEmbedder()
    llm_client = NvidiaChatClient() if llm_summaries else None
    summarizer = RepoSummarizer(llm_client=llm_client)
    chunker = TreeSitterChunker()

    if raw_url.lower() == "local" or raw_url.rstrip("/") == LOCAL_REPO_URL:
        files = load_repository_files(BACKEND_DIR)
        chunks = chunker.chunk_all(files)
        repo_url_key = LOCAL_REPO_URL
        branch_label = branch if branch and branch.lower() != "default" else "main"
    else:
        cloner = RepoCloner(raw_url, branch=branch or None)
        try:
            repo_dir = cloner.clone()
            files = load_repository_files(repo_dir)
            chunks = chunker.chunk_all(files)
            repo_url_key = raw_url.rstrip("/")
            branch_label = cloner.resolved_branch
        finally:
            cloner.cleanup()

    if not chunks:
        raise ValueError("No indexable source files found in repository.")

    repo_id = store.index_chunks(
        repo_url=repo_url_key,
        chunks=chunks,
        embedder=embedder,
        branch=branch_label,
        files=files,
        include_summaries=True,
        summarizer=summarizer,
        llm_summaries=llm_summaries,
    )
    repo_meta = store.get_repository(repo_id) or {}
    return {
        "repo_id": repo_id,
        "repo_url": repo_url_key,
        "file_count": len(files),
        "ast_chunk_count": len(chunks),
        "total_indexed_chunks": repo_meta.get("chunk_count", len(chunks)),
        **store.last_sync_stats,
    }


async def _heartbeat_loop(job_store: IndexJobStore, job_id: str) -> None:
    """Periodically extends the job lease while an indexing job is actively running."""
    while True:
        await asyncio.sleep(settings.INDEX_JOB_HEARTBEAT_SECONDS)
        try:
            await asyncio.to_thread(job_store.heartbeat, job_id, settings.INDEX_JOB_LEASE_SECONDS)
        except Exception:
            pass


async def _run_job_record(job: dict[str, Any], job_store: IndexJobStore) -> None:
    """Executes a claimed indexing job with periodic lease heartbeats and updates its terminal status."""
    job_id = str(job.get("id") or job.get("job_id") or "")
    repo_url = str(job.get("repo_url") or "")
    branch = str(job.get("branch") or "main")
    llm_summaries = bool(job.get("llm_summaries", False))
    lock_key = LOCAL_REPO_URL if repo_url.lower() == "local" else repo_url.rstrip("/")
    lock = _SYNC_LOCKS.setdefault(lock_key, asyncio.Lock())

    heartbeat_task = asyncio.create_task(_heartbeat_loop(job_store, job_id))
    try:
        async with lock:
            stats = await asyncio.to_thread(_execute_ingest, repo_url, branch, llm_summaries)
        await asyncio.to_thread(job_store.succeed, job_id, stats=stats)
    except Exception as exc:
        try:
            await asyncio.to_thread(job_store.fail, job_id, str(exc))
        except Exception:
            pass
    finally:
        heartbeat_task.cancel()


async def _claim_and_run_once() -> None:
    """Claims and executes one queued job from `index_jobs` if available."""
    try:
        job_store = IndexJobStore()
        claimed = await asyncio.to_thread(
            job_store.claim_next, _WORKER_ID, settings.INDEX_JOB_LEASE_SECONDS
        )
        if claimed:
            await _run_job_record(claimed, job_store=job_store)
    except Exception:
        pass


async def _background_job_worker_loop() -> None:
    """Claims queued jobs from `index_jobs` (and sweeps expired leases) in the background."""
    while True:
        await asyncio.sleep(settings.INDEX_JOB_POLL_SECONDS)
        if not (settings.NVIDIA_API_KEY and settings.SUPABASE_URL and settings.SUPABASE_KEY):
            continue
        try:
            job_store = IndexJobStore()
            await asyncio.to_thread(job_store.sweep_expired)
            claimed = await asyncio.to_thread(
                job_store.claim_next, _WORKER_ID, settings.INDEX_JOB_LEASE_SECONDS
            )
            if claimed:
                await _run_job_record(claimed, job_store=job_store)
        except Exception:
            pass


async def _background_local_sync_loop() -> None:
    """Watches the local workspace and enqueues an incremental sync job when saved files change."""
    while True:
        await asyncio.sleep(15)
        if not (settings.NVIDIA_API_KEY and settings.SUPABASE_URL and settings.SUPABASE_KEY):
            continue
        try:
            store = SupabaseVectorStore()
            repos = await asyncio.to_thread(store.list_repositories)
            local_repo = next((r for r in repos if r.get("repo_url") == LOCAL_REPO_URL), None)
            if not local_repo:
                continue

            repo_id = str(local_repo["id"])
            full_meta = await asyncio.to_thread(store.get_repository, repo_id)
            old_hashes = (full_meta or {}).get("file_hashes")
            if not isinstance(old_hashes, dict) or not old_hashes:
                continue

            files = await asyncio.to_thread(load_repository_files, BACKEND_DIR)
            new_hashes = build_file_manifest(files)
            if new_hashes != old_hashes:
                job_store = IndexJobStore()
                await asyncio.to_thread(
                    job_store.enqueue,
                    repo_id,
                    LOCAL_REPO_URL,
                    str(local_repo.get("branch") or "main"),
                    "incremental",
                    False,
                )
        except Exception:
            pass


@asynccontextmanager
async def lifespan(_app: FastAPI):
    sync_task = asyncio.create_task(_background_local_sync_loop())
    worker_task = asyncio.create_task(_background_job_worker_loop())
    try:
        yield
    finally:
        sync_task.cancel()
        worker_task.cancel()


app = FastAPI(title="Codebase Copilot API", version="0.2.0", lifespan=lifespan)

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


class CreateConversationRequest(BaseModel):
    title: str = "New chat"


@dataclass
class AuthContext:
    """Request-scoped auth context; plug JWT/Supabase Auth verification here when auth is enabled."""
    user_id: str | None = None
    access_token: str | None = None


def get_auth_context(
    authorization: str | None = Header(default=None),
    x_user_id: str | None = Header(default=None),
) -> AuthContext:
    token = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip() or None
    return AuthContext(user_id=x_user_id, access_token=token)


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


@app.get("/api/repos/{repo_id}/conversations")
def list_conversations(repo_id: str) -> dict[str, Any]:
    try:
        store = SupabaseVectorStore()
        if not store.get_repository(repo_id):
            raise HTTPException(status_code=404, detail="Repository not found.")
        return {"conversations": store.list_conversations(repo_id)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/repos/{repo_id}/conversations")
def create_conversation(repo_id: str, req: CreateConversationRequest) -> dict[str, Any]:
    try:
        store = SupabaseVectorStore()
        if not store.get_repository(repo_id):
            raise HTTPException(status_code=404, detail="Repository not found.")
        conversation_id = store.create_conversation(repo_id=repo_id, title=req.title.strip() or "New chat")
        conversation = store.get_conversation(conversation_id)
        return {"conversation": conversation}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/conversations/{conversation_id}/messages")
def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(default=4, ge=1, le=50),
    before_id: int | None = Query(default=None, ge=1),
) -> dict[str, Any]:
    try:
        store = SupabaseVectorStore()
        conversation = store.get_conversation(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found.")
        messages, has_more = store.get_conversation_messages(
            conversation_id, limit=limit, before_id=before_id
        )
        return {
            "conversation": conversation,
            "messages": messages,
            "has_more": has_more,
            "next_before_id": messages[0]["id"] if has_more and messages else None,
        }
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ingest")
async def ingest_repository(
    req: IngestRequest,
    _auth: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    raw_url = req.repo_url.strip()
    if not raw_url:
        raise HTTPException(status_code=400, detail="Repository URL is required.")

    lock_key = LOCAL_REPO_URL if raw_url.lower() == "local" else raw_url.rstrip("/")
    lock = _SYNC_LOCKS.setdefault(lock_key, asyncio.Lock())
    try:
        async with lock:
            return await asyncio.to_thread(_execute_ingest, raw_url, req.branch, req.llm_summaries)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/repos/{repo_id}/reindex")
async def reindex_repository(
    repo_id: str,
    background_tasks: BackgroundTasks,
    wait: bool = Query(default=False),
    _auth: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    """Queues a background incremental re-index job (or runs synchronously when `?wait=true`)."""
    try:
        store = SupabaseVectorStore()
        repo = await asyncio.to_thread(store.get_repository, repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found.")
        repo_url = str(repo["repo_url"])
        branch = str(repo.get("branch") or "main")

        if wait:
            lock = _SYNC_LOCKS.setdefault(repo_url, asyncio.Lock())
            async with lock:
                return await asyncio.to_thread(_execute_ingest, repo_url, branch, False)

        job_store = IndexJobStore()
        row = await asyncio.to_thread(
            job_store.enqueue, repo_id, repo_url, branch, "incremental", False
        )
        background_tasks.add_task(_claim_and_run_once)
        return public_job(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/repos/{repo_id}/sync")
async def sync_repository_async(
    repo_id: str,
    background_tasks: BackgroundTasks,
    _auth: AuthContext = Depends(get_auth_context),
) -> dict[str, Any]:
    """Queues an asynchronous incremental SHA-256 sync job for an existing repository."""
    try:
        store = SupabaseVectorStore()
        repo = await asyncio.to_thread(store.get_repository, repo_id)
        if not repo:
            raise HTTPException(status_code=404, detail="Repository not found.")
        repo_url = str(repo["repo_url"])
        branch = str(repo.get("branch") or "main")

        job_store = IndexJobStore()
        row = await asyncio.to_thread(
            job_store.enqueue, repo_id, repo_url, branch, "incremental", False
        )
        background_tasks.add_task(_claim_and_run_once)
        return public_job(row)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/jobs/{job_id}")
def get_index_job(job_id: str) -> dict[str, Any]:
    """Returns the current status and stats of a background indexing job."""
    try:
        job_store = IndexJobStore()
        row = job_store.get(job_id)
        if not row:
            raise HTTPException(status_code=404, detail="Job not found.")
        return {"job": public_job(row)}
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.get("/api/repos/{repo_id}/jobs")
def list_repo_index_jobs(repo_id: str, limit: int = Query(default=10, ge=1, le=50)) -> dict[str, Any]:
    """Lists recent indexing jobs for a repository."""
    try:
        job_store = IndexJobStore()
        rows = job_store.list_for_repo(repo_id, limit=limit)
        return {"jobs": [public_job(r) for r in rows]}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


def _format_retrieved_chunks(chunks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
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
            "is_dependency_neighbor": bool(c.get("is_dependency_neighbor", False)),
            "content": c.get("content", ""),
        }
        for c in chunks
    ]


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
        )

        return {
            "answer": turn.answer,
            "original_query": turn.plan.original_query,
            "standalone_query": turn.plan.standalone_query,
            "needs_retrieval": turn.plan.needs_retrieval,
            "target_symbol": turn.plan.target_symbol,
            "target_file": turn.plan.target_file,
            "conversation_id": turn.conversation_id,
            "cited_chunk_ids": turn.cited_chunk_ids,
            "chunks": _format_retrieved_chunks(turn.retrieval.chunks),
            "timings_ms": turn.timings_ms,
        }
    except (QueryRewriteError, RerankerServiceError) as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/chat/stream")
def chat_with_repo_stream(req: ChatRequest) -> StreamingResponse:
    """Streams retrieved chunks and LLM answer tokens via Server-Sent Events (SSE)."""
    if not req.message or not req.message.strip():
        raise HTTPException(status_code=400, detail="Message cannot be empty.")

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

    def _event_generator() -> Iterator[str]:
        try:
            for event in engine.ask_stream(
                user_message=req.message,
                repo_id=req.repo_id,
                conversation_id=conv_id,
            ):
                if event["type"] == "metadata":
                    plan = event["plan"]
                    retrieval = event["retrieval"]
                    payload = {
                        "type": "metadata",
                        "conversation_id": event["conversation_id"],
                        "original_query": plan.original_query,
                        "standalone_query": plan.standalone_query,
                        "needs_retrieval": plan.needs_retrieval,
                        "target_symbol": plan.target_symbol,
                        "target_file": plan.target_file,
                        "chunks": _format_retrieved_chunks(retrieval.chunks),
                    }
                    yield f"data: {json.dumps(payload)}\n\n"
                else:
                    yield f"data: {json.dumps(event)}\n\n"
        except Exception as exc:
            yield f"data: {json.dumps({'type': 'error', 'detail': str(exc)})}\n\n"

    return StreamingResponse(_event_generator(), media_type="text/event-stream")


FRONTEND_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(FRONTEND_DIR)), name="static")


@app.get("/")
def serve_frontend() -> FileResponse:
    return FileResponse(str(FRONTEND_DIR / "index.html"))


def main() -> None:
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)


if __name__ == "__main__":
    main()
