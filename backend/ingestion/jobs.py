from datetime import datetime, timedelta, timezone
from typing import Any
from supabase import Client
from config import settings

ACTIVE_STATUSES = ("queued", "running")
TERMINAL_STATUSES = ("succeeded", "failed")
DEFAULT_LEASE_SECONDS = 900
MAX_ATTEMPTS = 2

_JOB_COLUMNS = (
    "id,repo_id,kind,status,repo_url,branch,llm_summaries,base_run_id,target_run_id,"
    "stats,error,attempt,worker_id,requested_at,started_at,finished_at,heartbeat_at,lease_expires_at"
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(value: datetime) -> str:
    return value.isoformat()


class IndexJobStore:
    """Durable queue for indexing work.

    A job is a row, not a request-scoped task: it survives a process restart, can be
    polled by the client, and is claimed under a lease so multiple workers (or
    replicas) cannot run the same repository twice.
    """

    def __init__(self, client: Client | None = None, url: str | None = None, key: str | None = None) -> None:
        if client is not None:
            self.client = client
            return

        supabase_url = url if url is not None else settings.SUPABASE_URL
        supabase_key = key if key is not None else settings.SUPABASE_KEY
        if not supabase_url or not supabase_key:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY are required. Set them in your .env file.")
        self.client = create_client(supabase_url, supabase_key)

    # ---------- enqueue / read ----------

    def enqueue(
        self,
        repo_id: str,
        repo_url: str,
        branch: str = "main",
        kind: str = "incremental",
        llm_summaries: bool = False,
    ) -> dict[str, Any]:
        """Queues a job, returning the existing active one if this repo already has work pending.

        The partial unique index on (repo_id) where status in ('queued','running') is what
        makes this idempotent across processes, so double-clicking "sync" cannot start two runs.
        """
        payload = {
            "repo_id": repo_id,
            "repo_url": repo_url,
            "branch": branch,
            "kind": kind,
            "llm_summaries": llm_summaries,
            "status": "queued",
        }

        for _ in range(3):
            try:
                res = self.client.table("index_jobs").insert(payload).execute()
                if res.data:
                    return dict(res.data[0])
            except Exception as exc:
                message = str(exc).lower()
                if "duplicate" not in message and "unique" not in message:
                    raise

            existing = self.active_for_repo(repo_id)
            if existing is not None:
                return existing

        raise RuntimeError(f"Could not queue an indexing job for repository {repo_id}")

    def get(self, job_id: str) -> dict[str, Any] | None:
        res = self.client.table("index_jobs").select(_JOB_COLUMNS).eq("id", job_id).execute()
        return dict(res.data[0]) if res.data else None

    def active_for_repo(self, repo_id: str) -> dict[str, Any] | None:
        res = (
            self.client.table("index_jobs")
            .select(_JOB_COLUMNS)
            .eq("repo_id", repo_id)
            .in_("status", list(ACTIVE_STATUSES))
            .order("requested_at", desc=True)
            .limit(1)
            .execute()
        )
        return dict(res.data[0]) if res.data else None

    def list_for_repo(self, repo_id: str, limit: int = 20) -> list[dict[str, Any]]:
        res = (
            self.client.table("index_jobs")
            .select(_JOB_COLUMNS)
            .eq("repo_id", repo_id)
            .order("requested_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [dict(row) for row in (res.data or [])]

    def recent(self, limit: int = 20) -> list[dict[str, Any]]:
        res = (
            self.client.table("index_jobs")
            .select(_JOB_COLUMNS)
            .order("requested_at", desc=True)
            .limit(limit)
            .execute()
        )
        return [dict(row) for row in (res.data or [])]

    # ---------- worker side ----------

    def claim_next(self, worker_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> dict[str, Any] | None:
        """Atomically claims the oldest queued job, or returns None if the queue is empty."""
        res = self.client.rpc(
            "claim_next_index_job",
            {"p_worker_id": worker_id, "p_lease_seconds": lease_seconds},
        ).execute()
        rows = res.data or []
        if isinstance(rows, dict):
            rows = [rows]
        return dict(rows[0]) if rows else None

    def heartbeat(self, job_id: str, lease_seconds: int = DEFAULT_LEASE_SECONDS) -> None:
        """Extends the lease so a long embedding run is not mistaken for a crashed worker."""
        now = _utc_now()
        self.client.table("index_jobs").update(
            {
                "heartbeat_at": _iso(now),
                "lease_expires_at": _iso(now + timedelta(seconds=lease_seconds)),
            }
        ).eq("id", job_id).eq("status", "running").execute()

    def succeed(
        self,
        job_id: str,
        stats: dict[str, Any] | None = None,
        target_run_id: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "status": "succeeded",
            "finished_at": _iso(_utc_now()),
            "stats": stats or {},
            "error": "",
            "lease_expires_at": None,
        }
        if target_run_id:
            payload["target_run_id"] = target_run_id
        self.client.table("index_jobs").update(payload).eq("id", job_id).execute()

    def fail(self, job_id: str, error: str) -> None:
        self.client.table("index_jobs").update(
            {
                "status": "failed",
                "finished_at": _iso(_utc_now()),
                "error": (error or "")[:2000],
                "lease_expires_at": None,
            }
        ).eq("id", job_id).execute()

    def sweep_expired(self) -> dict[str, int]:
        """Recovers jobs whose worker died: requeue once, then mark failed.

        Without this, a crash mid-index leaves a repo permanently "running" and the partial
        unique index blocks every future sync for that repository.
        """
        res = (
            self.client.table("index_jobs")
            .select("id,attempt")
            .eq("status", "running")
            .lt("lease_expires_at", _iso(_utc_now()))
            .execute()
        )

        requeued = 0
        failed = 0
        for row in res.data or []:
            job_id = str(row["id"])
            if int(row.get("attempt") or 0) < MAX_ATTEMPTS:
                self.client.table("index_jobs").update(
                    {
                        "status": "queued",
                        "worker_id": "",
                        "lease_expires_at": None,
                        "started_at": None,
                        "error": "requeued after lease expiry",
                    }
                ).eq("id", job_id).execute()
                requeued += 1
            else:
                self.fail(job_id, "Job lease expired and retry limit was reached.")
                failed += 1

        return {"requeued": requeued, "failed": failed}


def public_job(row: dict[str, Any]) -> dict[str, Any]:
    """Serializes a job row for the API (keeps the shape stable for the UI)."""
    stats = row.get("stats")
    return {
        "job_id": str(row.get("id") or ""),
        "repo_id": str(row.get("repo_id") or ""),
        "kind": row.get("kind") or "incremental",
        "status": row.get("status") or "queued",
        "repo_url": row.get("repo_url") or "",
        "branch": row.get("branch") or "main",
        "attempt": int(row.get("attempt") or 0),
        "stats": stats if isinstance(stats, dict) else {},
        "error": row.get("error") or "",
        "requested_at": row.get("requested_at"),
        "started_at": row.get("started_at"),
        "finished_at": row.get("finished_at"),
    }
