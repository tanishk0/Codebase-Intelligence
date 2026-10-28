# Codebase Copilot - Backend

High-performance codebase ingestion, parsing, semantic AST chunking, and vector embedding engine for Codebase Copilot.

## Architecture

- **`config.py`**: Pydantic-based configuration loading `.env` credentials (`SUPABASE_URL`, `SUPABASE_KEY`, `NVIDIA_API_KEY`), embedding model parameters, and file filters.
- **`ingestion/git_clone.py`**: Safe GitHub URL validation and shallow (`depth=1`) cloning to temporary workspaces.
- **`ingestion/loader.py`**: Fast recursive directory scanner filtering non-code, binaries, and oversized files.
- **`ingestion/chunker.py`**: Tree-sitter powered AST chunker supporting Python, JavaScript, TypeScript, and TSX with intelligent class/method/preamble extraction and sliding fallback for documentation and configs.
- **`ingestion/embedder.py`**: Batched NVIDIA NIM embedding client (`nvidia/nemotron-3.5-embed-1b`, 1024-dim) with passage/query asymmetric encoding, automatic truncation, and rate-limit retry backoff.
- **`ingestion/vector_store.py`**: Supabase (`pgvector`) vector store manager handling idempotent repository upserts, batched chunk insertion, and cosine similarity RPC search.
- **`supabase_schema.sql`**: SQL setup script enabling `pgvector`, creating `repositories` and `code_chunks` tables, HNSW index, and the `match_code_chunks` RPC function.

## Setup & Running Tests

```bash
# 1. Install dependencies with uv
uv sync

# 2. Run unit test suite
uv run python -m unittest discover -s tests -v

# 3. Run live NVIDIA + Supabase smoke test (after running supabase_schema.sql in Supabase SQL Editor)
uv run python tests/smoke_test_embeddings.py
```
