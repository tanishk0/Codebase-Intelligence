# Arcline / Codebase Copilot

Arcline indexes a GitHub repository and answers questions about its code with file and line citations. The application consists of a React/Vite frontend and a Python/FastAPI backend using NVIDIA NIM and Supabase Postgres/pgvector.

## Setup

Requirements: Python 3.11+, uv, Node.js/npm, Git, a Supabase project running Postgres 15+, and NVIDIA API access to the configured embedding, reranking, and chat models.

1. Copy `.env.example` to `.env` at the repository root and fill in the credentials. `SUPABASE_KEY` must be a backend secret/service-role key. `SUPABASE_ANON_KEY` is a separate public publishable/anon key used for sign-in.
2. For a new database, run `backend/supabase_schema.sql` in Supabase's SQL Editor. For an existing database, run `backend/migrations/001_workspace_ownership.sql` before starting this version.
3. Enable Google in Supabase Authentication providers, configure its Google OAuth credentials, and allow `http://localhost:5173/workspace` as a redirect URL. Add your production `/workspace` URL when deploying.
4. Install and start the backend:

   ```powershell
   cd backend
   uv sync --locked
   uv run python main.py
   ```

5. In another terminal, install and start the frontend:

   ```powershell
   cd frontend
   npm ci
   npm run dev
   ```

Open `http://localhost:5173`, sign in, and add a GitHub repository. Vite proxies `/api` to the backend on port 8000.

For a production frontend build, run `npm run build` in `frontend`, then start the backend. It serves the built application at `http://127.0.0.1:8000/` and `/workspace`. Update OAuth redirect URLs for that origin.

## How it works

Git clone → safe text-file loading → Tree-sitter chunks and dependency analysis → summaries and NVIDIA embeddings → Supabase index.

Questions → optional follow-up rewriting → semantic and BM25 search → reciprocal rank fusion → model reranking → headers and one-hop caller context → cited, streamed answer.

Python, JavaScript, TypeScript, JSX, and TSX receive AST-aware parsing; other text files use line-based chunks. Full index builds activate a new run after embedding succeeds. Incremental updates reuse unchanged files and atomically replace changed files in bounded groups; the entire incremental repository update is not one transaction. Reindex jobs persist in Supabase with worker leases and heartbeats.

The special `local` repository indexes only this checkout's `backend/` directory. While the backend runs, it checks registered local indexes every 15 seconds. Environment files and `.pem`/`.key` files are excluded from ingestion.

## Workspace access and migration

All repository, conversation, message, job, ingestion, and chat API routes require a verified Supabase Bearer token. The API checks repository ownership, and users can independently index the same repository URL. Each user currently has one index per URL; choosing another branch updates that index.

Browser clients use Supabase for authentication only. Database tables and application RPCs are restricted to the backend service role by the schema/migration.

Existing repositories without an `owner_id` are retained but hidden from user workspaces. Sign in and re-ingest them to create an owned index. An administrator can instead explicitly assign the correct Supabase user UUID to `repositories.owner_id` in SQL; conversation access follows the parent repository. The migration never guesses ownership.

The root `pyproject.toml`, `src/`, `app/`, and root `tests/` are ignored legacy prototype files, retained locally for compatibility. The supported application and dependency lock live under `backend/`; the frontend lives under `frontend/`.

## Verification

```powershell
cd backend
uv run python -m unittest discover -s tests -v
```

The unit suite mocks external APIs. Live smoke scripts under `backend/tests/smoke_test_*.py` contact GitHub/NVIDIA/Supabase and may incur API usage. They are separate from unit verification.

See `backend/README.md` for the module map and model settings.
