-- Run this script in your Supabase SQL Editor to set up pgvector, tables, and the similarity search RPC.
-- Safe to re-run: every statement is idempotent.

-- 1. Enable the pgvector extension
create extension if not exists vector;

-- 2. Repositories table (tracks indexed GitHub repositories)
--    active_run_id points at the chunk set currently served by search. Re-indexing writes a new run,
--    then flips this pointer in a single-row update, so search never sees a half-written index.
create table if not exists public.repositories (
    id uuid primary key default gen_random_uuid(),
    repo_url text not null unique,
    branch text not null default 'main',
    chunk_count integer not null default 0,
    active_run_id uuid,
    embed_model text,
    embedding_dim integer,
    indexed_at timestamptz not null default now()
);

-- Upgrade path if an older version of this table already exists
alter table public.repositories add column if not exists active_run_id uuid;
alter table public.repositories add column if not exists embed_model text;
alter table public.repositories add column if not exists embedding_dim integer;

-- 3. Code chunks table (maps 1:1 to CodeChunk + 1024-dim NVIDIA nemotron-3.5-embed-1b vector)
create table if not exists public.code_chunks (
    id bigserial primary key,
    repo_id uuid not null references public.repositories(id) on delete cascade,
    run_id uuid not null,
    file_path text not null,
    content text not null,
    start_line integer not null,
    end_line integer not null,
    node_type text not null,
    parent_class text not null default '',
    embedding vector(1024) not null,
    created_at timestamptz not null default now()
);

alter table public.code_chunks add column if not exists run_id uuid;

-- 4. Indexes for fast filtering & HNSW cosine vector search
create index if not exists idx_code_chunks_repo_id on public.code_chunks(repo_id);
create index if not exists idx_code_chunks_repo_run on public.code_chunks(repo_id, run_id);

create index if not exists idx_code_chunks_embedding_hnsw
    on public.code_chunks
    using hnsw (embedding vector_cosine_ops);

-- 5. Security: lock tables down. RLS on with NO policies means the publishable/anon key
--    can neither read nor write. Only the backend's secret (service_role) key, which bypasses RLS, has access.
alter table public.repositories enable row level security;
alter table public.code_chunks enable row level security;

-- 6. RPC function for semantic cosine similarity search (only serves each repo's active run)
create or replace function public.match_code_chunks(
    query_embedding vector(1024),
    match_repo_id uuid default null,
    match_count int default 10,
    similarity_threshold float default 0.2
)
returns table (
    id bigint,
    repo_id uuid,
    file_path text,
    content text,
    start_line int,
    end_line int,
    node_type text,
    parent_class text,
    similarity float
)
language sql stable
set search_path = public, extensions
as $$
    select
        cc.id,
        cc.repo_id,
        cc.file_path,
        cc.content,
        cc.start_line,
        cc.end_line,
        cc.node_type,
        cc.parent_class,
        1 - (cc.embedding <=> query_embedding) as similarity
    from public.code_chunks cc
    join public.repositories r
      on r.id = cc.repo_id
     and r.active_run_id = cc.run_id
    where (match_repo_id is null or cc.repo_id = match_repo_id)
      and 1 - (cc.embedding <=> query_embedding) >= similarity_threshold
    order by cc.embedding <=> query_embedding
    limit match_count;
$$;

-- Only the backend (service_role) may call the search function
revoke execute on function public.match_code_chunks(vector, uuid, int, float) from public, anon, authenticated;
grant execute on function public.match_code_chunks(vector, uuid, int, float) to service_role;
