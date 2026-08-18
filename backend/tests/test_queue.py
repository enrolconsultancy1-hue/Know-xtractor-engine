"""Tests for the in-process job queue."""

import threading
import time

from app.services.queue import AnalysisQueue


def test_queue_runs_job_to_completion():
    q = AnalysisQueue(max_workers=2)
    done = threading.Event()
    result: dict = {}

    def fn(job):
        job.set_progress("working", 0.5)
        result["ran"] = True
        done.set()

    q.submit(1, fn)
    assert done.wait(timeout=5), "job did not complete"
    job = q.get(1)
    assert job.status == "done"
    assert result["ran"] is True


def test_queue_failure_is_captured():
    q = AnalysisQueue(max_workers=1)
    done = threading.Event()

    def fn(job):
        done.set()
        raise RuntimeError("boom")

    q.submit(2, fn)
    assert done.wait(timeout=5)
    # Give the worker a moment to mark failure.
    time.sleep(0.2)
    job = q.get(2)
    assert job.status == "failed"
    assert "RuntimeError" in (job.error or "")


def test_queue_cancel_sets_flag():
    q = AnalysisQueue(max_workers=1)
    q.submit(3, lambda job: None)
    assert q.cancel(3) is True
    assert q.get(3).cancel_requested is True
