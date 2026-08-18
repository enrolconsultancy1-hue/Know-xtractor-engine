"""Tests for the queue backend selection and RQ adapter."""

import pytest

from app.core.config import Settings


def test_queue_backend_defaults_to_inprocess():
    assert Settings().queue_backend == "inprocess"


def test_worker_module_imports():
    # rq is a hard dependency; importing the worker must not require Redis.
    import app.worker  # noqa: F401


def test_rq_queue_roundtrip_skips_without_redis():
    redis = pytest.importorskip("redis")
    try:
        redis.from_url("redis://localhost:6379/0").ping()
    except Exception:
        pytest.skip("Redis not available on localhost:6379")

    from app.services.rq_queue import RQQueue

    q = RQQueue(name="knox-test")
    # A trivial no-op task proves enqueue works against a live Redis.
    job = q._queue.enqueue("app.worker.execute_task", {"dummy": True}, 999999)
    assert job is not None
