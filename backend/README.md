# Arcline backend

FastAPI API for repository ingestion, incremental indexing, hybrid retrieval, and conversational code Q&A. See the root [README](../README.md) for credentials, database migration, Google OAuth, and frontend setup.

## Run

From this directory:

```powershell
uv sync --locked
uv run python main.py
```

The backend listens on `127.0.0.1:8000`. Vite development runs separately on port 5173. A built `frontend/dist` is served by FastAPI at `/` and `/workspace`.

## Modules

- `config.py`: Pydantic settings from root `.env` and optional `backend/.env` overrides.
- `main.py`: API routes, verified Google/Supabase authentication, repository ownership checks, streaming chat, and background worker lifecycle.
- `ingestion/git_clone.py`: HTTPS GitHub validation and temporary shallow clones with default-branch detection.
- `ingestion/loader.py`: bounded text loading, deterministic file hashes, path/symlink checks, and environment/private-key file exclusions.
- `ingestion/chunker.py`: AST chunks for Python/JS/TS/JSX/TSX, symbol metadata, class headers, identifier splitting, and fallback text chunks.
- `ingestion/dependency.py`: import, inheritance, and call relationships, including aliases and barrel resolution.
- `ingestion/summarizer.py`: file/repository outlines and optional LLM-enriched summaries.
- `ingestion/embedder.py`: batched NVIDIA embeddings with query/passage encoding, request limits, and retries.
- `ingestion/vector_store.py`: Supabase storage, owner-specific repository identity, full-run activation, incremental file replacements, BM25/semantic search fusion, and conversation persistence.
- `ingestion/jobs.py`: durable indexing jobs with atomic claims, leases, heartbeats, and expired-job recovery.
- `retrieval/query_router.py`: follow-up rewriting, file/symbol hints, and retrieval skipping for greetings/meta questions. Code questions share one hybrid retrieval path.
- `retrieval/reranker.py`: NVIDIA cross-encoder ranking and context merging/budgeting.
- `retrieval/retriever.py`: hybrid search, prior-chunk carry-over, reranking, and context expansion with headers and up to four one-hop callers.
- `retrieval/chat_engine.py`: grounded cited answers, streaming, recent-turn memory, rolling summaries, and persistence.
- `supabase_schema.sql`: complete idempotent schema for fresh installs.
- `migrations/001_workspace_ownership.sql`: ownership and backend-only database access for existing installs. Apply before using the updated API.

## Models and limits

Defaults in `config.py` use `nvidia/llama-nemotron-embed-vl-1b-v2` with 1024-dimensional embeddings, `nvidia/llama-nemotron-rerank-vl-1b-v2` for reranking, and `nvidia/nemotron-3-ultra-550b-a55b` for answers. `NVIDIA_FAST_MODEL` is a separately configurable setting for rewrites and summaries; it currently defaults to the same model as answers. Override these settings in `.env` as needed.

Retrieval defaults to 40 candidates, eight final chunks, and a 6,000-token code-context budget. Loading is capped at 2,000 files, 500 KB per file, and 50 MB total source. The `local` input indexes this backend directory, with change detection every 15 seconds while running.

Full builds preserve the live run until activation. Incremental sync replaces bounded file groups atomically within the current run; a failure after an earlier group commits can leave a partially updated repository until retry.

## Tests

```powershell
uv run python -m unittest discover -s tests -v
```

Unit tests mock external services and include API authentication/ownership coverage. On Windows, symlink creation may cause one test to skip. Async tests require permission to create local event-loop sockets.

Optional live checks (network access and configured services required):

```powershell
uv run python tests/smoke_test_ingestion.py
uv run python tests/smoke_test_embeddings.py
```

The embedding smoke test writes an ownerless maintenance index, which is deliberately absent from user workspaces.
