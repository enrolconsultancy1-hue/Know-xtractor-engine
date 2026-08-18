"""FastAPI application entrypoint."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import Settings, get_settings
from app.core.logging import setup_logging

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

    from app.api import analysis, architecture, knowledge, projects

    prefix = settings.api_prefix
    app.include_router(projects.router, prefix=prefix)
    app.include_router(analysis.router, prefix=prefix)
    app.include_router(knowledge.router, prefix=prefix)
    app.include_router(architecture.router, prefix=prefix)

    @app.get(f"{prefix}/health")
    def health() -> dict:
        return {"status": "ok", "app": settings.app_name, "version": settings.version}

    @app.get("/")
    def root() -> dict:
        return {"app": settings.app_name, "docs": "/docs", "api": prefix}

    return app


app = create_app()
