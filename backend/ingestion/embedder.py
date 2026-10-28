from dataclasses import dataclass
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import time
from typing import Callable, Iterator, Literal
import httpx
from config import settings
from ingestion.chunker import CodeChunk

# Only these are worth retrying; 4xx like 400/401/403/404/410 are permanent and should fail fast.
RETRYABLE_STATUS = {429, 500, 502, 503, 504}
MAX_BACKOFF_SECONDS = 60.0


@dataclass
class EmbeddedChunk:
    chunk: CodeChunk
    embedding: list[float]


class EmbeddingError(RuntimeError):
    """Raised when the embedding API fails permanently or exhausts retries."""


class RateLimiter:
    """Minimal client-side limiter that spaces requests to stay under a requests-per-minute budget."""

    def __init__(
        self,
        requests_per_minute: int,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.min_interval = 60.0 / requests_per_minute if requests_per_minute > 0 else 0.0
        self._clock = clock
        self._sleep = sleep
        self._next_allowed = 0.0

    def wait(self) -> None:
        now = self._clock()
        if now < self._next_allowed:
            self._sleep(self._next_allowed - now)
            now = self._next_allowed
        self._next_allowed = now + self.min_interval


def parse_retry_after(value: str | None) -> float | None:
    """Parse a Retry-After header, which may be delta-seconds or an HTTP date."""
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        retry_at = parsedate_to_datetime(value)
        if retry_at.tzinfo is None:
            retry_at = retry_at.replace(tzinfo=timezone.utc)
        return max(0.0, (retry_at - datetime.now(timezone.utc)).total_seconds())
    except (TypeError, ValueError):
        return None


class NvidiaEmbedder:
    """Generates vector embeddings for code chunks and search queries via NVIDIA NIM API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
        batch_size: int | None = None,
        requests_per_minute: int | None = None,
        max_retries: int = 5,
        timeout: float = 30.0,
        sleep: Callable[[float], None] = time.sleep,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.NVIDIA_API_KEY
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is missing. Set it in your .env file.")

        self.base_url = (base_url or settings.NVIDIA_BASE_URL).rstrip("/")
        self.model = model or settings.NVIDIA_EMBED_MODEL
        self.dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
        self.batch_size = batch_size or settings.EMBED_BATCH_SIZE
        self.max_retries = max_retries
        self.timeout = timeout
        self._sleep = sleep
        rpm = requests_per_minute if requests_per_minute is not None else settings.NVIDIA_REQUESTS_PER_MINUTE
        self.rate_limiter = rate_limiter or RateLimiter(rpm, sleep=sleep)

    def _backoff(self, attempt: int, response: httpx.Response | None = None) -> float:
        retry_after = parse_retry_after(response.headers.get("Retry-After")) if response is not None else None
        delay = retry_after if retry_after is not None else 2 ** (attempt + 1)
        return min(delay, MAX_BACKOFF_SECONDS)

    def _embed_batch(
        self,
        texts: list[str],
        input_type: Literal["passage", "query"],
        client: httpx.Client,
    ) -> list[list[float]]:
        if not texts:
            return []

        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "input": texts,
            "model": self.model,
            "input_type": input_type,
            "dimensions": self.dimensions,
            "encoding_format": "float",
            "truncate": "END",
        }

        for attempt in range(self.max_retries + 1):
            is_last = attempt == self.max_retries
            self.rate_limiter.wait()

            try:
                response = client.post(url, headers=headers, json=payload)
            except httpx.TransportError as exc:
                # Network-level failure (timeout, connection reset): transient, retry.
                if is_last:
                    raise EmbeddingError(f"Embedding request failed after {attempt + 1} attempts: {exc}") from exc
                self._sleep(self._backoff(attempt))
                continue

            if response.status_code in RETRYABLE_STATUS:
                if is_last:
                    raise EmbeddingError(
                        f"Embedding API returned {response.status_code} after {attempt + 1} attempts: "
                        f"{response.text[:200]}"
                    )
                self._sleep(self._backoff(attempt, response))
                continue

            if response.status_code >= 400:
                # Permanent client error (bad key, retired model, bad payload): fail fast, no retries.
                raise EmbeddingError(
                    f"Embedding API returned {response.status_code} for model '{self.model}': {response.text[:200]}"
                )

            items = sorted(response.json()["data"], key=lambda item: item["index"])
            vectors = [item["embedding"] for item in items]
            if len(vectors) != len(texts):
                raise EmbeddingError(f"Expected {len(texts)} embeddings, got {len(vectors)}")
            return vectors

        raise EmbeddingError("Unreachable: retry loop exited without result")  # pragma: no cover

    def iter_embedded_batches(
        self,
        texts: list[str],
        input_type: Literal["passage", "query"] = "passage",
    ) -> Iterator[list[list[float]]]:
        """Yields embeddings batch by batch so callers can persist incrementally."""
        with httpx.Client(timeout=self.timeout) as client:
            for start in range(0, len(texts), self.batch_size):
                yield self._embed_batch(texts[start : start + self.batch_size], input_type=input_type, client=client)

    def embed_texts(
        self,
        texts: list[str],
        input_type: Literal["passage", "query"] = "passage",
    ) -> list[list[float]]:
        """Embeds a list of strings in batches."""
        all_embeddings: list[list[float]] = []
        for batch in self.iter_embedded_batches(texts, input_type=input_type):
            all_embeddings.extend(batch)
        return all_embeddings

    def embed_query(self, query: str) -> list[float]:
        """Embeds a single user search query using input_type='query'."""
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty.")
        return self.embed_texts([query], input_type="query")[0]

    def iter_embedded_chunks(self, chunks: list[CodeChunk]) -> Iterator[list[EmbeddedChunk]]:
        """Yields EmbeddedChunk batches aligned with the embedding batch size."""
        texts = [c.content for c in chunks]
        offset = 0
        for vectors in self.iter_embedded_batches(texts, input_type="passage"):
            batch_chunks = chunks[offset : offset + len(vectors)]
            offset += len(vectors)
            yield [EmbeddedChunk(chunk=c, embedding=v) for c, v in zip(batch_chunks, vectors, strict=True)]

    def embed_chunks(self, chunks: list[CodeChunk]) -> list[EmbeddedChunk]:
        """Embeds a list of CodeChunk objects and returns EmbeddedChunk instances."""
        result: list[EmbeddedChunk] = []
        for batch in self.iter_embedded_chunks(chunks):
            result.extend(batch)
        return result
