"""Tests for the queue backend selection and RQ adapter."""

from unittest.mock import MagicMock, patch

import pytest

from app.core.config import Settings
from app.services.rq_queue import RQQueue
from app.worker import execute_task


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

    q = RQQueue(name="knox-test")
    # A trivial no-op task proves enqueue works against a live Redis.
    job = q._queue.enqueue("app.worker.execute_task", {"dummy": True}, 999999)
    assert job is not None


def test_rq_queue_submit_mocked():
    with patch("redis.from_url") as mock_from_url:
        mock_conn = MagicMock()
        mock_from_url.return_value = mock_conn

        q = RQQueue(name="knox-mock")
        q._queue = MagicMock()

        q.submit(42, {"branch": "main"})
        q._queue.enqueue.assert_called_once()
        call_args = q._queue.enqueue.call_args
        assert call_args[0][0] == "app.worker.execute_task"
        assert call_args[0][1] == {"branch": "main"}
        assert call_args[0][2] == 42


def test_rq_queue_cancel_mocked():
    with patch("redis.from_url"):
        q = RQQueue(name="knox-mock")
        mock_job1 = MagicMock()
        mock_job1.args = ({"task": 1}, 10)
        mock_job2 = MagicMock()
        mock_job2.args = ({"task": 2}, 20)

        q._queue = MagicMock()
        q._queue.get_jobs.return_value = [mock_job1, mock_job2]

        # Cancel existing job
        assert q.cancel(20) is True
        mock_job2.cancel.assert_called_once()

        # Cancel non-existent job
        assert q.cancel(999) is False


def test_rq_queue_pending_count_mocked():
    with patch("redis.from_url"):
        q = RQQueue(name="knox-mock")
        q._queue = MagicMock()
        q._queue.get_jobs.return_value = [MagicMock(), MagicMock(), MagicMock()]
        assert q.pending_count() == 3


def test_rq_queue_ping_mocked():
    with patch("redis.from_url"):
        q = RQQueue(name="knox-mock")
        q._queue = MagicMock()

        # Successful ping
        q._queue.connection.ping.return_value = True
        assert q.ping() is True

        # Failed ping
        q._queue.connection.ping.side_effect = ConnectionError("Redis down")
        assert q.ping() is False


def test_worker_execute_task():
    with patch("app.services.runner.run_task") as mock_run_task:
        execute_task({"project_id": 1}, 123)
        mock_run_task.assert_called_once_with({"project_id": 1}, 123)
