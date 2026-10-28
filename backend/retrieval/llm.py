import json
import re
import time
from typing import Any, Callable
import httpx
from config import settings
from ingestion.embedder import MAX_BACKOFF_SECONDS, RETRYABLE_STATUS, RateLimiter, parse_retry_after

_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>", re.DOTALL | re.IGNORECASE)
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


class LLMError(RuntimeError):
    """Raised when the NVIDIA NIM chat completion API fails."""


def strip_thinking(text: str) -> str:
    """Removes <think>...</think> reasoning blocks emitted by reasoning models."""
    return _THINK_BLOCK_RE.sub("", text).strip()


def extract_json_object(text: str) -> dict[str, Any]:
    """Extracts and parses a JSON object from an LLM response (handling markdown code fences)."""
    cleaned = strip_thinking(text)
    fence_match = _JSON_FENCE_RE.search(cleaned)
    candidate = fence_match.group(1) if fence_match else cleaned

    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end != -1 and end > start:
        candidate = candidate[start : end + 1]

    return json.loads(candidate)


class NvidiaChatClient:
    """Client for NVIDIA NIM chat completions supporting both fast utility calls and deep 550B answers."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        chat_model: str | None = None,
        fast_model: str | None = None,
        requests_per_minute: int | None = None,
        max_retries: int = 4,
        timeout: float = 60.0,
        sleep: Callable[[float], None] = time.sleep,
        rate_limiter: RateLimiter | None = None,
    ) -> None:
        self.api_key = api_key if api_key is not None else settings.NVIDIA_API_KEY
        if not self.api_key:
            raise ValueError("NVIDIA_API_KEY is missing. Set it in your .env file.")

        self.base_url = (base_url or settings.NVIDIA_BASE_URL).rstrip("/")
        self.chat_model = chat_model or settings.NVIDIA_CHAT_MODEL
        self.fast_model = fast_model or settings.NVIDIA_FAST_MODEL
        self.max_retries = max_retries
        self.timeout = timeout
        self._sleep = sleep
        rpm = requests_per_minute if requests_per_minute is not None else settings.NVIDIA_REQUESTS_PER_MINUTE
        self.rate_limiter = rate_limiter or RateLimiter(rpm, sleep=sleep)

    def _backoff(self, attempt: int, response: httpx.Response | None = None) -> float:
        retry_after = parse_retry_after(response.headers.get("Retry-After")) if response is not None else None
        delay = retry_after if retry_after is not None else 2 ** (attempt + 1)
        return min(delay, MAX_BACKOFF_SECONDS)

    def complete(
        self,
        messages: list[dict[str, str]],
        *,
        use_fast_model: bool = False,
        model: str | None = None,
        temperature: float = 0.1,
        max_tokens: int = 1024,
    ) -> str:
        """Runs a chat completion against NVIDIA NIM and returns the assistant message text."""
        chosen_model = model or (self.fast_model if use_fast_model else self.chat_model)
        url = f"{self.base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        payload = {
            "model": chosen_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        with httpx.Client(timeout=self.timeout) as client:
            for attempt in range(self.max_retries + 1):
                is_last = attempt == self.max_retries
                self.rate_limiter.wait()

                try:
                    response = client.post(url, headers=headers, json=payload)
                except httpx.TransportError as exc:
                    if is_last:
                        raise LLMError(f"Chat completion failed after {attempt + 1} attempts: {exc}") from exc
                    self._sleep(self._backoff(attempt))
                    continue

                if response.status_code in RETRYABLE_STATUS:
                    if is_last:
                        raise LLMError(
                            f"Chat API returned {response.status_code} after {attempt + 1} attempts: "
                            f"{response.text[:200]}"
                        )
                    self._sleep(self._backoff(attempt, response))
                    continue

                if response.status_code >= 400:
                    raise LLMError(
                        f"Chat API returned {response.status_code} for model '{chosen_model}': "
                        f"{response.text[:200]}"
                    )

                msg = response.json()["choices"][0]["message"]
                content = msg.get("content") or msg.get("reasoning_content") or ""
                return strip_thinking(content)

        raise LLMError("Unreachable: retry loop exited without result")  # pragma: no cover

    def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        use_fast_model: bool = True,
        max_tokens: int = 512,
    ) -> dict[str, Any]:
        """Runs a completion and parses the JSON object response."""
        raw = self.complete(
            messages,
            use_fast_model=use_fast_model,
            temperature=0.0,
            max_tokens=max_tokens,
        )
        return extract_json_object(raw)

