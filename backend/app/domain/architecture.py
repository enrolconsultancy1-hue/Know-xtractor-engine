"""Architecture models: discovery report, reconstruction, customization."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Confidence, Evidence


class ArchitecturePattern(BaseModel):
    """A detected architectural pattern with evidence and confidence."""

    name: str
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[str] = Field(default_factory=list)


class ArchitectureLayer(BaseModel):
    """A dynamically inferred logical layer (not forced categories)."""

    name: str
    purpose: str = ""
    components: list[str] = Field(default_factory=list)
    confidence: Confidence = Confidence(score=0.5)


class ArchitectureReport(BaseModel):
    """The architecture discovered from evidence."""

    patterns: list[ArchitecturePattern] = Field(default_factory=list)
    primary_pattern: str = ""
    confidence: float = 0.0
    layers: list[ArchitectureLayer] = Field(default_factory=list)
    service_boundaries: list[str] = Field(default_factory=list)
    entry_points: list[str] = Field(default_factory=list)
    evidence: list[Evidence] = Field(default_factory=list)

    def summary(self) -> str:
        return (
            f"{self.primary_pattern or 'undetermined'} "
            f"(confidence {self.confidence:.2f})"
        )


class CustomizationRequest(BaseModel):
    """User-driven technology substitutions for reconstruction."""

    frontend_technology: str | None = None
    backend_technology: str | None = None
    database: str | None = None
    deployment_strategy: str | None = None
    architecture_pattern: str | None = None
    authentication: str | None = None
    infrastructure: str | None = None
    notes: str = ""


class TechnologyBinding(BaseModel):
    """Mapping of an architectural concern to a concrete technology."""

    concern: str  # e.g. "http-api", "persistence", "frontend"
    original: str = ""
    selected: str
    rationale: str = ""


class ReconstructedArchitecture(BaseModel):
    """The technology-neutral (then bound) architecture."""

    essential_capabilities: list[str] = Field(default_factory=list)
    domain_model: list[str] = Field(default_factory=list)
    components: list[dict] = Field(default_factory=list)
    architectural_requirements: list[str] = Field(default_factory=list)
    technology_bindings: list[TechnologyBinding] = Field(default_factory=list)
    data_relationships: list[str] = Field(default_factory=list)
    workflows: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    principles: list[str] = Field(default_factory=list)
    notes: str = ""
