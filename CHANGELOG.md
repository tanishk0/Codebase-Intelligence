# Changelog

## v1.0.0 — 2026-11-26

The first versioned release of Arcline, a repository assistant for understanding code through cited, conversational answers.

### Features

- GitHub repository ingestion with Tree-sitter parsing, dependency analysis, summaries, NVIDIA embeddings, and Supabase storage.
- Semantic and BM25 retrieval with rank fusion, model reranking, and context expansion.
- Streamed answers with file/line citations, persistent conversations, and follow-up context.
- Incremental indexing and durable reindex jobs with leases and heartbeats.
- Google sign-in and user-specific repository indexes and conversation access.
- Minimal black, charcoal, and silver interface with borderless assistant responses, collapsed source disclosures, keyboard focus states, and scroll behavior that respects reading earlier messages.

### Fixes

- Require verified tokens and repository ownership across workspace APIs; ignore client-supplied identity headers.
- Restrict database tables and application RPCs to the backend service role.
- Exclude environment files and private-key files from ingestion.
- Correct OAuth redirects, authenticated logout, and session cleanup.
- Support `/workspace` refreshes and serve only public frontend assets through the static route.
- Declare and lock the backend server dependencies and document complete setup instructions.

### Upgrading an existing installation

1. Apply `backend/migrations/001_workspace_ownership.sql` in the Supabase SQL Editor before starting this version. New installations can use the complete `backend/supabase_schema.sql`.
2. Set `SUPABASE_ANON_KEY` to the public publishable/anon key, alongside the backend secret/service-role `SUPABASE_KEY`.
3. Allow your frontend `/workspace` URL in Supabase's OAuth redirect settings.
4. Existing ownerless indexes remain stored but hidden. Re-ingest while signed in, or explicitly assign the correct user UUID to the repository's `owner_id` as an administrator.

### Validation and limits

- Backend suite: 62 tests, 61 passed and one Windows symlink test skipped.
- Frontend production build passed; neutral styling and simulated streaming were reviewed in the browser.
- Live NVIDIA/Supabase flows and the database migration have not been executed as part of this release verification.
- Incremental updates commit bounded file groups; the entire repository update is not a single transaction.
