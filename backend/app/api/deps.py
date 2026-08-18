"""Shared API dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.core.config import Settings, get_settings
from app.core.ratelimit import default_limiter


def settings() -> Settings:
    return get_settings()


def require_rate_limit(request: Request) -> None:
    """Reject with 429 when the client exceeds the configured request rate."""
    key = request.client.host if request.client else "unknown"
    if not default_limiter.allow(key):
        raise HTTPException(429, "Rate limit exceeded. Please retry later.")
