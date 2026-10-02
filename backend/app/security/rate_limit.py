"""Bounded in-memory rate limiting for the reference deployment."""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True, slots=True)
class RateLimitRule:
    limit: int
    window_seconds: int


class RateLimitExceeded(RuntimeError):
    """Raised when one principal exceeds a configured request budget."""

    def __init__(self, retry_after: int) -> None:
        super().__init__("Request rate limit exceeded")
        self.retry_after = retry_after


class InMemoryRateLimiter:
    """Thread-safe fixed-window limiter; production should use a distributed store."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._requests: dict[str, deque[float]] = {}

    def check(self, key: str, rule: RateLimitRule, *, now: float | None = None) -> None:
        current = time.monotonic() if now is None else now
        cutoff = current - rule.window_seconds
        with self._lock:
            bucket = self._requests.setdefault(key, deque())
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()
            if len(bucket) >= rule.limit:
                retry_after = max(1, int(rule.window_seconds - (current - bucket[0])))
                raise RateLimitExceeded(retry_after)
            bucket.append(current)

    def clear(self) -> None:
        with self._lock:
            self._requests.clear()


__all__ = ["InMemoryRateLimiter", "RateLimitExceeded", "RateLimitRule"]
