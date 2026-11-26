-- Apply to an existing installation before starting the updated backend.
-- Existing ownerless repositories remain private to backend maintenance tools.
begin;

alter table public.repositories add column if not exists owner_id uuid;
alter table public.repositories drop constraint if exists repositories_repo_url_key;
create unique index if not exists idx_repositories_owner_url
    on public.repositories (owner_id, repo_url) nulls not distinct;

-- Browser clients use Supabase Auth only. Application data goes through the API,
-- which verifies the JWT and repository ownership using a backend service key.
alter table public.repositories enable row level security;
alter table public.code_chunks enable row level security;
alter table public.conversations enable row level security;
alter table public.messages enable row level security;
alter table public.index_jobs enable row level security;

revoke all on table public.repositories, public.code_chunks,
    public.conversations, public.messages, public.index_jobs
    from public, anon, authenticated;
grant all on table public.repositories, public.code_chunks,
    public.conversations, public.messages, public.index_jobs to service_role;
grant usage, select on sequence public.code_chunks_id_seq, public.messages_id_seq to service_role;

-- SECURITY DEFINER functions otherwise bypass RLS. Revoke PostgreSQL's default
-- PUBLIC execute privilege as well as the previous explicit browser grants.
revoke all on function
    public.hybrid_search_code_chunks(vector, text, uuid, int, int),
    public.semantic_search_code_chunks(vector, uuid, int),
    public.bm25_search_code_chunks(text, uuid, int),
    public.claim_next_index_job(text, int),
    public.copy_chunks_to_run(uuid, uuid, uuid, text[]),
    public.replace_file_chunks(uuid, uuid, text[], jsonb)
    from public, anon, authenticated;
grant execute on function
    public.hybrid_search_code_chunks(vector, text, uuid, int, int),
    public.semantic_search_code_chunks(vector, uuid, int),
    public.bm25_search_code_chunks(text, uuid, int),
    public.claim_next_index_job(text, int),
    public.copy_chunks_to_run(uuid, uuid, uuid, text[]),
    public.replace_file_chunks(uuid, uuid, text[], jsonb)
    to service_role;

commit;
