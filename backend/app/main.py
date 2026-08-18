"""FastAPI application entrypoint."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.logging import setup_logging
from app.db import init_db

setup_logging()


def create_app() -> FastAPI:
    settings = get_settings()
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

    init_db()
    return app


app = create_app()
