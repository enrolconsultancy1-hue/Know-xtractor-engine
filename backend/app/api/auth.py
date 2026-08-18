"""Authentication dependencies.

KNOX_AUTH_MODE controls the protection applied to mutating endpoints:

- ``none``  (default): open — convenient for local development.
- ``token`` : shared-secret bearer token (single-tenant self-host).

``users`` (JWT + per-user project scoping) is the intended multi-tenant
extension and is intentionally not wired yet; requesting it returns 503 rather
than silently falling back to open access.
"""

from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.config import get_settings

_bearer = HTTPBearer(auto_error=False)


def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Gate a route on KNOX_AUTH_MODE; returns None when the request is allowed."""
    settings = get_settings()
    if settings.auth_mode == "none":
        return
    if settings.auth_mode == "token":
        expected = settings.api_key
        if not expected:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "Auth enabled but KNOX_API_KEY is not configured",
            )
        if credentials is None or credentials.credentials != expected:
            raise HTTPException(
                status.HTTP_401_UNAUTHORIZED,
                "Invalid or missing API key",
            )
        return
    raise HTTPException(
        status.HTTP_503_SERVICE_UNAVAILABLE,
        f"Unsupported auth mode: {settings.auth_mode}",
    )
