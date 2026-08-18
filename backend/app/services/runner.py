"""Background analysis runner with in-process live progress tracking.

For a single-process deployment this is sufficient. A production deployment
would move this to Celery/RQ; the pipeline itself is transport-agnostic.
"""

from __future__ import annotations

import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import get_settings
from app.db import SessionLocal
from app.db.models import AnalysisRun, Project
from app.services.acquisition import AcquisitionError, acquire_repository
from app.services.exporter import export_package
from app.services.pipeline import AnalysisPipeline, PipelineContext

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


def start_analysis(project_id: int, url: str, branch: str = "main", commit_ref: str | None = None) -> int:
    """Create an AnalysisRun and start a background thread."""
    settings = get_settings()
    session = SessionLocal()
    try:
        run = AnalysisRun(project_id=project_id, status="pending", stage="queued")
        session.add(run)
        session.commit()
        run_id = run.id
    finally:
        session.close()

    _runs[run_id] = {
        "status": "running", "stage": "repository_acquisition", "progress": 0.0,
        "errors": [], "warnings": [], "events": [],
    }

    def worker() -> None:
        db = SessionLocal()
        try:
            project = db.get(Project, project_id)
            repo_name = url.rstrip("/").split("/")[-1].removesuffix(".git")
            workspace = settings.workspace_dir / str(project_id)

            _emit(run_id, "repository_acquisition", 0.02, "Cloning repository")
            try:
                repo_path = acquire_repository(url, workspace, branch, commit_ref)
            except AcquisitionError as exc:
                _finish(db, run_id, "failed", errors=[str(exc)])
                return

            ctx = PipelineContext(
                repository=repo_name, source_url=url, repo_path=str(repo_path),
            )
            pipeline = AnalysisPipeline()
            try:
                pkg = pipeline.run(ctx, lambda s, p, m: _emit(run_id, s, p, m))
            except Exception as exc:  # noqa: BLE001
                _finish(db, run_id, "failed", errors=[f"{type(exc).__name__}: {exc}",
                                                       *ctx.errors, *ctx.warnings])
                return

            # Persist the knowledge package.
            pkg_dir = settings.packages_dir
            pkg_path = pkg_dir / f"project_{project_id}.json"
            pkg_path.write_text(pkg.model_dump_json(indent=2), encoding="utf-8")
            try:
                export_package(pkg, "markdown", settings.exports_dir)
            except Exception:  # noqa: BLE001
                pass

            summary = pkg.stats()
            summary["package_path"] = str(pkg_path)
            _finish(db, run_id, "done", summary=summary, warnings=list(ctx.warnings))
        except Exception as exc:  # noqa: BLE001
            _finish(db, run_id, "failed", errors=[f"{type(exc).__name__}: {exc}"])
        finally:
            db.close()

    t = threading.Thread(target=worker, daemon=True)
    t.start()
    return run_id


def _finish(db, run_id: int, status: str, summary: dict | None = None,
            errors: list[str] | None = None, warnings: list[str] | None = None) -> None:
    run = db.get(AnalysisRun, run_id)
    if run:
        run.status = status
        run.stage = status
        run.progress = 1.0
        run.finished_at = datetime.now(timezone.utc)
        run.errors = errors or []
        run.warnings = warnings or []
        run.summary = summary or {}
        db.commit()
    _update(run_id, status=status, stage=status, progress=1.0,
            errors=errors or [], warnings=warnings or [])


def load_package(project_id: int) -> dict[str, Any] | None:
    """Load a previously stored knowledge package for a project."""
    settings = get_settings()
    path = settings.packages_dir / f"project_{project_id}.json"
    if path.exists():
        import json

        return json.loads(path.read_text(encoding="utf-8"))
    return None


def package_path(project_id: int) -> Path:
    return get_settings().packages_dir / f"project_{project_id}.json"
