# Codebase Copilot - Backend

High-performance codebase ingestion, AST chunking, hierarchical summarization, hybrid RRF retrieval, and conversational RAG engine for Codebase Copilot.

## Architecture

### Ingestion (`ingestion/`)
- **`config.py`**: Pydantic-based configuration loading `.env` credentials (`SUPABASE_URL`, `SUPABASE_KEY`, `NVIDIA_API_KEY`), Nemotron model parameters, and retrieval budgets.
- **`ingestion/git_clone.py`**: Safe GitHub URL validation and shallow (`depth=1`) cloning to temporary workspaces (automatically detecting default branches).
- **`ingestion/loader.py`**: Fast recursive directory scanner rejecting symlinks/path escapes, binaries, and oversized files.
- **`ingestion/chunker.py`**: Tree-sitter powered AST chunker supporting Python, JavaScript, TypeScript, and TSX with symbol extraction, oversized function splitting, class headers, and camelCase/snake_case identifier splitting for full-text search.
- **`ingestion/summarizer.py`**: Outline-based file and repository summarizer (`file_summary` chunks + `repo_summary` overview) with optional batched LLM enrichment.
- **`ingestion/embedder.py`**: Batched NVIDIA NIM embedding client (`nvidia/nemotron-3.5-embed-1b`, 1024-dim) with passage/query asymmetric encoding, client-side rate limiting, and retry backoff.
- **`ingestion/vector_store.py`**: Crash-safe Supabase (`pgvector` + FTS) store with atomic `run_id` swaps, hybrid RRF search, symbol lookup, context neighbor queries, and multi-turn conversation storage.

### Retrieval & Conversational RAG (`retrieval/`)
- **`retrieval/llm.py`**: Dual-tier NVIDIA NIM chat client pairing `nvidia/nemotron-3-ultra-550b-a55b` (deep code answers) with `nvidia/nemotron-3.5-bolt-e4b` (fast query rewriting & batched summaries).
- **`retrieval/query_router.py`**: Rewrites ambiguous follow-up questions using chat history and routes queries (`symbol`, `file`, `overview`, or `hybrid`).
- **`retrieval/reranker.py`**: Code-aware reranker (symbol/file boosts, identifier overlap, carry-over bonus, per-file diversity caps) and `ContextAssembler` (attaching class headers & file preambles, merging overlapping spans, and enforcing token budgets).
- **`retrieval/retriever.py`**: End-to-end `CodebaseRetriever` orchestrating routing, hybrid RRF search, chunk carry-over, reranking, and context expansion.
- **`retrieval/chat_engine.py`**: `ConversationalRAGEngine` managing multi-turn history, rolling conversation summaries, cited chunk carry-over, and grounded `[file_path:Lstart-Lend]` answers.

## Setup & Running Tests

```bash
# 1. Install dependencies with uv
uv sync

# 2. Run unit test suite
uv run python -m unittest discover -s tests -v

# 3. Run live NVIDIA + Supabase smoke test (after running supabase_schema.sql in Supabase SQL Editor)
uv run python tests/smoke_test_embeddings.py
```
