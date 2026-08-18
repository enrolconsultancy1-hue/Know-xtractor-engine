"""Technology detection models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .common import Confidence, Evidence


class TechnologyKind(str, Enum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    DATABASE = "database"
    INFRASTRUCTURE = "infrastructure"
    LIBRARY = "library"
    TOOLING = "tooling"


class DependencyInfo(BaseModel):
    """A single dependency with architectural purpose and criticality."""

    name: str
    version: str | None = None
    kind: TechnologyKind = TechnologyKind.LIBRARY
    used_by: list[str] = Field(default_factory=list)
    purpose: str = ""
    architectural_layer: str = ""
    criticality: str = "unknown"  # critical | major | minor | unknown
    confidence: Confidence = Confidence(score=0.5, rationale="name-based inference")


class Technology(BaseModel):
    """A detected technology (language, framework, database, infra)."""

    name: str
    kind: TechnologyKind
    version: str | None = None
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)


class TechnologyStack(BaseModel):
    """The complete detected technology stack."""

    languages: list[Technology] = Field(default_factory=list)
    frameworks: list[Technology] = Field(default_factory=list)
    databases: list[Technology] = Field(default_factory=list)
    infrastructure: list[Technology] = Field(default_factory=list)
    dependencies: list[DependencyInfo] = Field(default_factory=list)

    @property
    def summary(self) -> dict[str, list[str]]:
        def names(items: list[Technology]) -> list[str]:
            return sorted({i.name for i in items})

        return {
            "languages": names(self.languages),
            "frameworks": names(self.frameworks),
            "databases": names(self.databases),
            "infrastructure": names(self.infrastructure),
        }
