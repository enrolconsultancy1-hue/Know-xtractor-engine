"""The canonical KnowledgePackage — the central, source-independent output."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from pydantic import BaseModel, Field

from .api_model import ApiSpec
from .architecture import ArchitectureReport, ReconstructedArchitecture
from .component import Component
from .data_model import DataModel
from .implementation import ImplementationSpec
from .sprint import EvolutionTimeline
from .technology import TechnologyStack
from .workflow import Workflow


class KnowledgeFact(BaseModel):
    """A single extracted, classified, evidence-backed statement."""

    id: str
    fact: str
    kind: str = "fact"  # fact | inference | hypothesis
    confidence: float = Field(ge=0.0, le=1.0)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    category: str = ""


class KnowledgePackage(BaseModel):
    """The pure knowledge representation, independent of the original source.

    This model intentionally contains *understanding* (concepts, relationships,
    behavior, constraints, decisions) rather than a copy of the source code.
    """

    metadata: dict[str, Any] = Field(default_factory=dict)
    technologies: TechnologyStack = Field(default_factory=TechnologyStack)
    architecture: ArchitectureReport = Field(default_factory=ArchitectureReport)
    components: list[Component] = Field(default_factory=list)
    workflows: list[Workflow] = Field(default_factory=list)
    data_model: DataModel = Field(default_factory=DataModel)
    apis: ApiSpec = Field(default_factory=ApiSpec)
    integrations: list[str] = Field(default_factory=list)
    configuration: dict[str, Any] = Field(default_factory=dict)
    testing: list[dict[str, Any]] = Field(default_factory=list)
    security: list[str] = Field(default_factory=list)
    architectural_sprints: EvolutionTimeline = Field(default_factory=EvolutionTimeline)
    architectural_decisions: list[str] = Field(default_factory=list)
    invariants: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    patterns: list[str] = Field(default_factory=list)
    anti_patterns: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    facts: list[KnowledgeFact] = Field(default_factory=list)
    evidence: list[dict[str, Any]] = Field(default_factory=list)
    implementation_specification: ImplementationSpec = Field(default_factory=ImplementationSpec)
    reconstructed_architecture: ReconstructedArchitecture = Field(
        default_factory=ReconstructedArchitecture
    )

    @classmethod
    def new(cls, repository: str, source_url: str = "") -> KnowledgePackage:
        return cls(
            metadata={
                "repository": repository,
                "source_url": source_url,
                "generated_at": datetime.now(UTC).isoformat(),
                "schema_version": "1.0",
            }
        )

    def stats(self) -> dict[str, Any]:
        """Quick summary statistics for dashboards."""
        return {
            "technologies": self.technologies.summary,
            "component_count": len(self.components),
            "workflow_count": len(self.workflows),
            "api_count": len(self.apis.endpoints),
            "entity_count": len(self.data_model.entities),
            "sprint_count": len(self.architectural_sprints.sprints),
            "fact_count": len(self.facts),
            "confidence": round(self.architecture.confidence, 2),
            "primary_pattern": self.architecture.primary_pattern,
        }
