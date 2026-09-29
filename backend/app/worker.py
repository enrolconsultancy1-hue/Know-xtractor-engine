"""RQ worker entrypoint.

Run with::

    KNOX_QUEUE_BACKEND=rq python -m app.worker

The worker listens on the ``knox`` Redis queue and executes analysis tasks.
"""

from __future__ import annotations

import redis
from rq import Queue, Worker

from app.core.config import get_settings


def execute_task(task: dict, run_id: int) -> None:
    """RQ target: run a serialized analysis task."""
    from app.services.runner import run_task

    run_task(task, run_id)


if __name__ == "__main__":
    import logging

    from app.core.logging import setup_logging

    setup_logging()
    logger = logging.getLogger("knox.worker")
    settings = get_settings()
    logger.info("starting RQ worker on %s", settings.redis_url)
    conn = redis.from_url(settings.redis_url)
    worker = Worker([Queue("knox", connection=conn)], connection=conn)
    worker.work()

