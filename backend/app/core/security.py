"""Security helpers for handling untrusted repositories.

KNOX treats every analyzed repository as untrusted input. This module
centralizes the guards that keep a repository from escaping its workspace or
causing harm during *static* analysis. KNOX never executes repository code.
"""

from __future__ import annotations

import re
from pathlib import Path

# Patterns that look like secrets we must never persist.
_SECRET_PATTERNS: list[tuple[str, str]] = [
    ("api_key", r"(?i)(api[_-]?key|apikey|access[_-]?token|auth[_-]?token)"),
    ("password", r"(?i)(password|passwd|pwd)"),
    ("secret", r"(?i)(secret|client[_-]?secret)"),
    ("private_key", r"(?i)(private[_-]?key|-----BEGIN)"),
    ("connection_string", r"(?i)(connection[_-]?string|database[_-]?url|dsn)"),
    ("token", r"(?i)(bearer|jwt[_-]?secret|refresh[_-]?token)"),
]

# Env var names that are always treated as secrets regardless of value.
_ALWAYS_SECRET_KEYS = {
    "password",
    "passwd",
    "pwd",
    "secret",
    "api_key",
    "apikey",
    "access_token",
    "auth_token",
    "private_key",
    "client_secret",
    "database_url",
    "dsn",
    "jwt_secret",
    "refresh_token",
    "aws_access_key_id",
    "aws_secret_access_key",
}

_SENSITIVE_VALUE_RE = re.compile(
    r"(?i)(password|passwd|secret|token|api[_-]?key|private[_-]?key)\s*[=:]\s*\S+"
)


def is_within(base: Path, target: Path) -> bool:
    """Return True if `target` resolves inside `base` (path-traversal guard)."""
    try:
        base_resolved = base.resolve()
        target_resolved = target.resolve()
    except OSError:
        return False
    return target_resolved == base_resolved or base_resolved in target_resolved.parents


def sanitize_path_segment(segment: str) -> str:
    """Sanitize a user-supplied path segment against traversal."""
    cleaned = segment.replace("\\", "/").lstrip("/")
    cleaned = re.sub(r"\.\.", "", cleaned)
    cleaned = re.sub(r"[^A-Za-z0-9._\-]", "_", cleaned)
    cleaned = cleaned.strip("._")
    return cleaned or "unnamed"


def classify_secret_key(key: str) -> str | None:
    """Return the secret category for an env/config key, or None if not secret."""
    k = key.strip().lower().replace("-", "_")
    # Specific, informative categories first.
    for category, pattern in _SECRET_PATTERNS:
        if re.search(pattern, k):
            return category
    # Generic always-secret keys not covered above (e.g. AWS keys).
    if k in _ALWAYS_SECRET_KEYS:
        return "credential"
    return None


def looks_like_secret_line(line: str) -> bool:
    """Heuristic: does this single config line carry a secret?"""
    return bool(_SENSITIVE_VALUE_RE.search(line))
