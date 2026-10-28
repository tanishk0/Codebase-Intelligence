-- Run this script in your Supabase SQL Editor to set up pgvector, unified hybrid search (RRF),
-- hierarchical summaries, and multi-turn conversation tables.
-- Safe to re-run: every statement is idempotent.

-- 1. Enable required extensions
create extension if not exists vector;

-- 2. Repositories table (tracks indexed GitHub repositories + repo-level summary)
create table if not exists public.repositories (
    id uuid primary key default gen_random_uuid(),
    repo_url text not null unique,
    branch text not null default 'main',
    chunk_count integer not null default 0,
    active_run_id uuid,
    embed_model text,
    embedding_dim integer,
    repo_summary text not null default '',
    indexed_at timestamptz not null default now()
);

alter table public.repositories add column if not exists active_run_id uuid;
alter table public.repositories add column if not exists embed_model text;
alter table public.repositories add column if not exists embedding_dim integer;
alter table public.repositories add column if not exists repo_summary text not null default '';

-- 3. Code chunks table (AST chunks, file summaries, symbol metadata, FTS tsvector, and 1024-dim vector)
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
    symbol_name text not null default '',
    search_text text not null default '',
    fts tsvector generated always as (to_tsvector('english', search_text)) stored,
    embedding vector(1024) not null,
    created_at timestamptz not null default now()
);

alter table public.code_chunks add column if not exists run_id uuid;
alter table public.code_chunks add column if not exists symbol_name text not null default '';
alter table public.code_chunks add column if not exists search_text text not null default '';
alter table public.code_chunks add column if not exists fts tsvector
    generated always as (to_tsvector('english', search_text)) stored;

-- 4. Indexes for fast filtering, symbol lookup, full-text search (GIN), & HNSW cosine vector search
create index if not exists idx_code_chunks_repo_id on public.code_chunks(repo_id);
create index if not exists idx_code_chunks_repo_run on public.code_chunks(repo_id, run_id);
create index if not exists idx_code_chunks_symbol on public.code_chunks(repo_id, symbol_name);
create index if not exists idx_code_chunks_file_path on public.code_chunks(repo_id, file_path);
create index if not exists idx_code_chunks_fts on public.code_chunks using gin (fts);

create index if not exists idx_code_chunks_embedding_hnsw
    on public.code_chunks
    using hnsw (embedding vector_cosine_ops);

-- 5. Multi-turn conversations and messages tables (stores cited chunk IDs for follow-up carry-over)
create table if not exists public.conversations (
    id uuid primary key default gen_random_uuid(),
    repo_id uuid references public.repositories(id) on delete cascade,
    title text not null default '',
    rolling_summary text not null default '',
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.messages (
    id bigserial primary key,
    conversation_id uuid not null references public.conversations(id) on delete cascade,
    role text not null check (role in ('user', 'assistant')),
    content text not null,
    standalone_query text not null default '',
    cited_chunk_ids bigint[] not null default '{}',
    created_at timestamptz not null default now()
);

create index if not exists idx_messages_conversation_id on public.messages(conversation_id, created_at);

-- 6. Security: lock all tables down with RLS. Only the backend's secret (service_role) key has access.
alter table public.repositories enable row level security;
alter table public.code_chunks enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;

-- 7. Unified Hybrid Search RPC: Reciprocal Rank Fusion (RRF) combining pgvector semantic search
--    + Postgres full-text keyword search (using OR-joined lexemes so natural language questions
--    still match code identifiers even when not every conversational word appears in the code).
create or replace function public.hybrid_search_code_chunks(
    query_embedding vector(1024),
    query_text text,
    match_repo_id uuid default null,
    match_count int default 30,
    rrf_k int default 60
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
    symbol_name text,
    similarity float,
    fts_rank float,
    rrf_score float
)
language sql stable
set search_path = public, extensions
as $$
    with active_chunks as (
        select cc.*
        from public.code_chunks cc
        join public.repositories r
          on r.id = cc.repo_id
         and r.active_run_id = cc.run_id
        where (match_repo_id is null or cc.repo_id = match_repo_id)
    ),
    ts_q as (
        select
            case
                when plainto_tsquery('english', coalesce(query_text, ''))::text = '' then null::tsquery
                else replace(plainto_tsquery('english', query_text)::text, ' & ', ' | ')::tsquery
            end as q
    ),
    semantic as (
        select
            ac.id,
            1 - (ac.embedding <=> query_embedding) as sim,
            row_number() over (order by ac.embedding <=> query_embedding) as vec_rank
        from active_chunks ac
        order by ac.embedding <=> query_embedding
        limit match_count * 2
    ),
    keyword as (
        select
            ac.id,
            ts_rank_cd(ac.fts, ts_q.q) as kw_score,
            row_number() over (
                order by ts_rank_cd(ac.fts, ts_q.q) desc
            ) as fts_pos
        from active_chunks ac
        cross join ts_q
        where ts_q.q is not null
          and ac.fts @@ ts_q.q
        order by kw_score desc
        limit match_count * 2
    ),
    fused as (
        select
            coalesce(s.id, k.id) as id,
            coalesce(s.sim, 0.0) as similarity,
            coalesce(k.kw_score, 0.0) as fts_rank,
            coalesce(1.0 / (rrf_k + s.vec_rank), 0.0)
              + coalesce(1.0 / (rrf_k + k.fts_pos), 0.0) as rrf_score
        from semantic s
        full outer join keyword k on s.id = k.id
    )
    select
        ac.id,
        ac.repo_id,
        ac.file_path,
        ac.content,
        ac.start_line,
        ac.end_line,
        ac.node_type,
        ac.parent_class,
        ac.symbol_name,
        f.similarity,
        f.fts_rank,
        f.rrf_score
    from fused f
    join active_chunks ac on ac.id = f.id
    order by f.rrf_score desc, f.similarity desc
    limit match_count;
$$;

-- Only the backend (service_role) may call the hybrid search RPC
revoke execute on function public.hybrid_search_code_chunks(vector, text, uuid, int, int)
    from public, anon, authenticated;
grant execute on function public.hybrid_search_code_chunks(vector, text, uuid, int, int)
    to service_role;
