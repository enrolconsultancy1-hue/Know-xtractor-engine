"""Redis/RQ-backed queue adapter (Phase 3).

Enqueues serializable analysis tasks onto a Redis/RQ queue; a separate worker
process (``python -m app.worker``) executes them. This gives hard isolation and
horizontal scaling that the in-process queue cannot provide.
"""

from __future__ import annotations

from typing import Any

import redis
from rq import Queue, Retry

from app.core.config import get_settings


class RQQueue:
    """Thin RQ adapter over a named Redis queue."""

    def __init__(self, name: str = "knox") -> None:
        self._queue = Queue(name, connection=redis.from_url(get_settings().redis_url))

    def submit(self, run_id: int, task: dict[str, Any]) -> None:
        self._queue.enqueue(
            "app.worker.execute_task",
            task,
            run_id,
            job_timeout=get_settings().analysis_timeout_seconds,
            retry=Retry(max=3, interval=5),
        )

    def cancel(self, run_id: int) -> bool:
        """Cancel a queued (not-yet-started) job; running jobs can't be force-stopped."""
        for job in self._queue.get_jobs():
            if len(job.args) >= 2 and job.args[1] == run_id:
                job.cancel()
                return True
        return False

    def pending_count(self) -> int:
        return len(self._queue.get_jobs())


rq_queue = RQQueue()
