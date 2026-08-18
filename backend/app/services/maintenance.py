"""Background maintenance: stale analysis-workspace cleanup."""

from __future__ import annotations

import shutil
import time
from pathlib import Path

from app.core.config import get_settings


def cleanup_stale_workspaces(max_age_days: int | None = None) -> int:
    """Remove analysis workspace directories older than ``max_age_days``.

    Returns the number of directories removed. A non-positive age disables the
    cleanup (returns 0).
    """
    settings = get_settings()
    if max_age_days is None:
        max_age_days = settings.stale_workspace_max_age_days
    if max_age_days <= 0:
        return 0

    workspace = Path(settings.workspace_dir)
    if not workspace.is_dir():
        return 0

    cutoff = time.time() - (max_age_days * 86400)
    removed = 0
    for child in workspace.iterdir():
        if not child.is_dir():
            continue
        try:
            if child.stat().st_mtime < cutoff:
                shutil.rmtree(child, ignore_errors=True)
                if not child.exists():
                    removed += 1
        except OSError:
            continue
    return removed
