"""In-memory sliding-window rate limiter (per client IP).

Suitable for single-instance deployments. Multi-instance deployments should
replace this with a Redis-backed limiter (same interface).
"""

from __future__ import annotations

import threading
import time
from collections import deque

from app.core.config import get_settings


class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def allow(self, key: str) -> bool:
        settings = get_settings()
        limit = settings.rate_limit_requests
        window = settings.rate_limit_window_seconds
        if limit <= 0:
            return True
        now = time.monotonic()
        with self._lock:
            dq = self._hits.setdefault(key, deque())
            while dq and dq[0] <= now - window:
                dq.popleft()
            if len(dq) >= limit:
                return False
            dq.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._hits.clear()


default_limiter = RateLimiter()
