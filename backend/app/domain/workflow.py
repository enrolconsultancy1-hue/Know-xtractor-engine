"""Workflow discovery models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Confidence, Evidence


class WorkflowStep(BaseModel):
    """A single node in a workflow graph."""

    id: str
    name: str
    kind: str = "step"  # trigger | transform | decision | external | output | error
    component_id: str | None = None
    description: str = ""
    dependencies: list[str] = Field(default_factory=list)
    side_effects: list[str] = Field(default_factory=list)


class WorkflowNode(BaseModel):
    """Alias-friendly node representation for the knowledge graph."""

    id: str
    label: str
    kind: str


class Workflow(BaseModel):
    """A discovered end-to-end workflow."""

    id: str
    name: str
    entry_point: str
    trigger: str = ""
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    error_paths: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)

    def nodes(self) -> list[WorkflowNode]:
        return [WorkflowNode(id=s.id, label=s.name, kind=s.kind) for s in self.steps]

    def edges(self) -> list[tuple[str, str]]:
        edges: list[tuple[str, str]] = []
        prev: str | None = None
        for s in self.steps:
            for dep in s.dependencies:
                edges.append((dep, s.id))
            if prev is not None and not s.dependencies:
                edges.append((prev, s.id))
            prev = s.id
        return edges
