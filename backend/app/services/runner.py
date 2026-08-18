"""Analysis runner backed by a pluggable job queue.

Submitting an analysis enqueues a serializable task on the configured backend:

- ``inprocess`` (default): an in-process FIFO queue with a worker pool
  (``services.queue.default_queue``).
- ``rq``: a Redis/RQ queue executed by a separate ``python -m app.worker``.

The analysis pipeline is unchanged; only the execution transport lives here.
"""

from __future__ import annotations

import concurrent.futures
import contextlib
import json
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.core import metrics
from app.core.config import get_settings
from app.db import SessionLocal
from app.db.models import AnalysisRun
from app.services.acquisition import AcquisitionError, acquire_repository
from app.services.exporter import export_package
from app.services.pipeline import AnalysisPipeline, PipelineContext
from app.services.queue import Job, default_queue

_runs: dict[int, dict[str, Any]] = {}
_lock = threading.Lock()


def run_state(run_id: int) -> dict[str, Any]:
    return dict(_runs.get(run_id, {"status": "unknown", "stage": "", "progress": 0.0}))


def _update(run_id: int, **fields: Any) -> None:
    with _lock:
        state = _runs.setdefault(run_id, {"status": "pending", "stage": "", "progress": 0.0,
                                          "errors": [], "warnings": [], "events": []})
        state.update(fields)


def _emit(run_id: int, stage: str, pct: float, message: str) -> None:
    _update(run_id, stage=stage, progress=pct)
    with _lock:
        _runs[run_id].setdefault("events", []).append({"stage": stage, "pct": pct, "message": message})


def start_analysis(project_id: int, url: str, branch: str = "main", commit_ref: str | None = None,
                   session: Any = None) -> int:
    """Create an AnalysisRun row and enqueue the analysis task.

    ``session`` is optional: request handlers pass their dependency-injected
    session so the run lands in the same DB/transaction as the project; the RQ
    worker and other background callers omit it to get a fresh ``SessionLocal``.
    """
    owns_session = session is None
    if session is None:
        session = SessionLocal()
    try:
        run = AnalysisRun(project_id=project_id, status="pending", stage="queued")
        session.add(run)
        session.commit()
        run_id = run.id
    finally:
        if owns_session:
            session.close()

    _runs[run_id] = {
        "status": "queued", "stage": "queued", "progress": 0.0,
        "errors": [], "warnings": [], "events": [],
    }

    task: dict[str, Any] = {
        "project_id": project_id, "url": url, "branch": branch,
        "commit_ref": commit_ref, "run_id": run_id,
    }
    if get_settings().queue_backend == "rq":
        from app.services.rq_queue import rq_queue

        rq_queue.submit(run_id, task)
    else:
        default_queue.submit(run_id, lambda job: execute_analysis(project_id, url, branch, commit_ref, run_id, job))
    return run_id


def run_task(task: dict[str, Any], run_id: int) -> None:
    """Execute a serialized analysis task (called by the RQ worker)."""
    execute_analysis(
        task["project_id"], task["url"], task["branch"], task["commit_ref"], run_id, None,
    )


def execute_analysis(project_id: int, url: str, branch: str, commit_ref: str | None,
                     run_id: int, job: Job | None) -> None:
    settings = get_settings()
    db = SessionLocal()
    started = time.monotonic()
    _update(run_id, started_monotonic=started)
    try:
        repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git")
        workspace = settings.workspace_dir / str(project_id)

        _emit(run_id, "repository_acquisition", 0.02, "Cloning repository")
        if job is not None:
            job.set_progress("repository_acquisition", 0.02)
        try:
            repo_path = acquire_repository(url, workspace, branch, commit_ref)
        except AcquisitionError as exc:
            _finish(db, run_id, "failed", errors=[str(exc)])
            return

        ctx = PipelineContext(repository=repo_name, source_url=url, repo_path=str(repo_path))
        pipeline = AnalysisPipeline()

        def progress(stage: str, pct: float, message: str) -> None:
            _emit(run_id, stage, pct, message)
            if job is not None:
                job.set_progress(stage, pct)
            _persist_progress(db, run_id, stage, pct)

        # Soft timeout (in-process workers can't be force-killed); hard
        # isolation comes from the RQ worker's job_timeout (Phase 3).
        executor = concurrent.futures.ThreadPoolExecutor(max_workers=1)
        future = executor.submit(pipeline.run, ctx, progress)
        try:
            pkg = future.result(timeout=settings.analysis_timeout_seconds)
        except TimeoutError:
            _finish(db, run_id, "failed",
                    errors=[f"Analysis timed out after {settings.analysis_timeout_seconds}s"])
            return
        except Exception as exc:  # noqa: BLE001
            _finish(db, run_id, "failed", errors=[f"{type(exc).__name__}: {exc}", *ctx.errors, *ctx.warnings])
            return
        finally:
            executor.shutdown(wait=False, cancel_futures=True)

        if job is not None and job.cancel_requested:
            _finish(db, run_id, "cancelled", summary={})
            return

        pkg_path = settings.packages_dir / f"project_{project_id}.json"
        pkg_path.write_text(pkg.model_dump_json(indent=2), encoding="utf-8")
        with contextlib.suppress(Exception):
            export_package(pkg, "markdown", settings.exports_dir)

        summary = pkg.stats()
        summary["package_path"] = str(pkg_path)
        _finish(db, run_id, "done", summary=summary, warnings=list(ctx.warnings))
    except Exception as exc:  # noqa: BLE001
        _finish(db, run_id, "failed", errors=[f"{type(exc).__name__}: {exc}"])
    finally:
        db.close()


def cancel_analysis(run_id: int) -> bool:
    """Request cooperative cancellation of a queued/running job."""
    if get_settings().queue_backend == "rq":
        from app.services.rq_queue import rq_queue

        rq_queue.cancel(run_id)
    default_queue.cancel(run_id)
    _update(run_id, status="cancelled", stage="cancelled")
    return True


def _persist_progress(db, run_id: int, stage: str, pct: float) -> None:
    run = db.get(AnalysisRun, run_id)
    if run:
        run.stage = stage
        run.progress = pct
        db.commit()


def _finish(db, run_id: int, status: str, summary: dict | None = None,
            errors: list[str] | None = None, warnings: list[str] | None = None) -> None:
    run = db.get(AnalysisRun, run_id)
    if run:
        run.status = status
        run.stage = status
        run.progress = 1.0
        run.finished_at = datetime.now(UTC)
        run.errors = errors or []
        run.warnings = warnings or []
        run.summary = summary or {}
        db.commit()
    _update(run_id, status=status, stage=status, progress=1.0,
            errors=errors or [], warnings=warnings or [])
    metrics.knox_analysis_runs_total.inc(labels={"status": status})
    started = run_state(run_id).get("started_monotonic")
    if isinstance(started, float):
        metrics.knox_analysis_duration_seconds.observe(time.monotonic() - started)


def load_package(project_id: int) -> dict[str, Any] | None:
    """Load a previously stored knowledge package for a project."""
    path = get_settings().packages_dir / f"project_{project_id}.json"
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return None


def package_path(project_id: int) -> Path:
    return get_settings().packages_dir / f"project_{project_id}.json"
