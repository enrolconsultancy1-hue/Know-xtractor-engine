"""Pluggable background job queue.

The default implementation is an in-process FIFO queue with a bounded worker
pool and cooperative cancellation — enough for a single-process deployment and
fully verifiable without external infrastructure.

For production, implement the same small interface on RQ / Celery / Dramatiq
and swap it in ``services/runner.py``; the analysis pipeline itself is
transport-agnostic and never needs to change.
"""

from __future__ import annotations

import queue
import threading
import traceback
from collections.abc import Callable


class Job:
    """A queued unit of work with observable state and cooperative cancellation."""

    def __init__(self, job_id: int, fn: Callable[[Job], None]) -> None:
        self.id = job_id
        self._fn = fn
        self.status = "queued"
        self.stage = "queued"
        self.progress = 0.0
        self.error: str | None = None
        self.cancel_requested = False

    def set_progress(self, stage: str, pct: float, message: str = "") -> None:
        self.stage = stage
        self.progress = pct

    def request_cancel(self) -> None:
        self.cancel_requested = True


class AnalysisQueue:
    """A simple FIFO job queue with a worker pool."""

    def __init__(self, max_workers: int = 1) -> None:
        self._q: queue.Queue[Job] = queue.Queue()
        self._jobs: dict[int, Job] = {}
        self._lock = threading.Lock()
        self._workers = [
            threading.Thread(target=self._worker, daemon=True, name=f"knox-worker-{i}")
            for i in range(max(1, max_workers))
        ]
        for w in self._workers:
            w.start()

    def submit(self, job_id: int, fn: Callable[[Job], None]) -> Job:
        job = Job(job_id, fn)
        with self._lock:
            self._jobs[job_id] = job
        self._q.put(job)
        return job

    def get(self, job_id: int) -> Job | None:
        with self._lock:
            return self._jobs.get(job_id)

    def cancel(self, job_id: int) -> bool:
        job = self.get(job_id)
        if job is None:
            return False
        job.request_cancel()
        return True

    def pending_count(self) -> int:
        return self._q.qsize()

    def _worker(self) -> None:
        while True:
            job = self._q.get()
            try:
                job.status = "running"
                try:
                    job._fn(job)
                except Exception as exc:  # noqa: BLE001 — a failed job must not kill the worker
                    job.status = "failed"
                    job.error = f"{type(exc).__name__}: {exc}"
                    job.progress = 1.0
                    traceback.print_exc()
                else:
                    job.status = "cancelled" if job.cancel_requested else "done"
                    job.progress = 1.0
            finally:
                self._q.task_done()


# Singleton used by the runner. Swap this for an RQ/Celery-backed implementation
# in production.
default_queue = AnalysisQueue(max_workers=1)
