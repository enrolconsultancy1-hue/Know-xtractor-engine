"""FastAPI application entrypoint."""

from __future__ import annotations

import logging
import threading
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from app.core import metrics
from app.core.config import Settings, get_settings
from app.core.context import request_id_var
from app.core.logging import setup_logging
from app.db import engine

setup_logging()


def _validate_production_config(settings: Settings) -> None:
    problems = settings.validate_production()
    if not problems:
        return
    logger = logging.getLogger(__name__)
    for p in problems:
        logger.error("production config error: %s", p)
    if settings.environment == "production":
        raise RuntimeError("Invalid production configuration:\n- " + "\n- ".join(problems))


def _record_request(request: Request, started: float, status: str) -> None:
    route = request.scope.get("route")
    path = route.path if route is not None else request.url.path
    labels = {"method": request.method, "path": path}
    metrics.http_requests_total.inc(labels={**labels, "status": status})
    metrics.http_request_duration_seconds.observe(time.monotonic() - started, labels=labels)


def _readiness() -> tuple[bool, str]:
    """Check DB connectivity and (for the RQ backend) queue connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception as exc:  # noqa: BLE001
        return False, f"database unavailable: {type(exc).__name__}"
    settings = get_settings()
    if settings.queue_backend == "rq":
        try:
            from app.services.rq_queue import rq_queue

            if not rq_queue.ping():
                return False, "queue unavailable: redis ping failed"
        except Exception as exc:  # noqa: BLE001
            return False, f"queue unavailable: {type(exc).__name__}"
    return True, "ok"


def _startup_stale_cleanup(settings: Settings) -> None:
    """Remove abandoned analysis workspaces older than the configured age."""
    from app.services.maintenance import cleanup_stale_workspaces

    def _run() -> None:
        try:
            removed = cleanup_stale_workspaces(settings.stale_workspace_max_age_days)
            if removed:
                logging.getLogger(__name__).info("removed %d stale workspace(s)", removed)
        except Exception:  # noqa: BLE001 — cleanup must never crash startup
            logging.getLogger(__name__).exception("stale workspace cleanup failed")

    threading.Thread(target=_run, daemon=True, name="knox-maintenance").start()


def create_app() -> FastAPI:
    settings = get_settings()
    _validate_production_config(settings)
    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        description="Knowledge eXtraction & Architectural Reconstruction Engine",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def _observe(request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        token = request_id_var.set(request_id)
        started = time.monotonic()
        try:
            response = await call_next(request)
        except Exception:
            _record_request(request, started, "500")
            request_id_var.reset(token)
            raise
        request_id_var.reset(token)
        _record_request(request, started, str(response.status_code))
        response.headers["X-Request-ID"] = request_id
        return response

    from app.api import analysis, architecture, knowledge, projects

    prefix = settings.api_prefix
    app.include_router(projects.router, prefix=prefix)
    app.include_router(analysis.router, prefix=prefix)
    app.include_router(knowledge.router, prefix=prefix)
    app.include_router(architecture.router, prefix=prefix)

    @app.get(f"{prefix}/health")
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "version": settings.version}

    @app.get("/healthz")
    def healthz() -> dict:
        return {"status": "ok"}

    @app.get("/readyz")
    def readyz() -> JSONResponse:
        ok, detail = _readiness()
        return JSONResponse(
            {"status": "ok" if ok else "not_ready", "detail": detail},
            status_code=200 if ok else 503,
        )

    @app.get("/metrics")
    def metrics_endpoint() -> Response:
        from app.services.queue import default_queue

        metrics.knox_queue_depth.set(float(default_queue.pending_count()))
        return Response(content=metrics.generate_latest(), media_type="text/plain; version=0.0.4; charset=utf-8")

    @app.get("/")
    def root() -> dict:
        return {"app": settings.app_name, "docs": "/docs", "api": prefix}

    _startup_stale_cleanup(settings)
    return app


app = create_app()
