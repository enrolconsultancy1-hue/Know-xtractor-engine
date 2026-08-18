"""API discovery models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Confidence, Evidence


class ApiEndpoint(BaseModel):
    """A discovered HTTP endpoint."""

    method: str
    path: str
    handler: str
    file: str
    line: int | None = None
    controller: str = ""
    summary: str = ""
    request_schema: str | None = None
    response_schema: str | None = None
    authentication: list[str] = Field(default_factory=list)
    middleware: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    framework: str = ""
    confidence: Confidence = Confidence(score=0.8)
    evidence: list[Evidence] = Field(default_factory=list)


class ApiSpec(BaseModel):
    """The complete extracted API surface."""

    framework: str = ""
    endpoints: list[ApiEndpoint] = Field(default_factory=list)
    base_path: str = ""
    confidence: Confidence = Confidence(score=0.5)

    def openapi_hint(self) -> dict:
        """Produce a minimal OpenAPI-compatible path map."""
        paths: dict[str, dict] = {}
        for ep in self.endpoints:
            paths.setdefault(ep.path, {})[ep.method.lower()] = {
                "summary": ep.summary,
                "operationId": ep.handler,
            }
        return {"openapi": "3.0.3", "info": {"title": "KNOX extracted API"}, "paths": paths}
