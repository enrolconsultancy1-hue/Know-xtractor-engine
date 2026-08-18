"""Request-scoped context variables (e.g. correlation IDs)."""

from __future__ import annotations

import contextvars

# Set by the observability middleware for the lifetime of a request; read by the
# JSON log formatter so every line from a given request carries the same ID.
request_id_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "request_id", default=None
)
