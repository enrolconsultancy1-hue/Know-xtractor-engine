"""Git history / architectural sprint models."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import Confidence, Evidence


class CommitInfo(BaseModel):
    sha: str
    short_sha: str
    message: str
    author: str
    timestamp: str
    files_changed: list[str] = Field(default_factory=list)


class ArchitecturalSprint(BaseModel):
    """A meaningful, clustered evolution of the system (not a raw commit)."""

    id: str
    name: str
    time_range: tuple[str, str] = ("", "")
    objective: str = ""
    architectural_changes: list[str] = Field(default_factory=list)
    components_added: list[str] = Field(default_factory=list)
    components_removed: list[str] = Field(default_factory=list)
    components_modified: list[str] = Field(default_factory=list)
    dependencies_added: list[str] = Field(default_factory=list)
    dependencies_removed: list[str] = Field(default_factory=list)
    behavior_changes: list[str] = Field(default_factory=list)
    migration_impact: str = ""
    architectural_significance: str = ""
    evidence: list[Evidence] = Field(default_factory=list)
    commits: list[CommitInfo] = Field(default_factory=list)
    confidence: Confidence = Confidence(score=0.5)


class EvolutionTimeline(BaseModel):
    """Chronological architectural evolution."""

    sprints: list[ArchitecturalSprint] = Field(default_factory=list)
    facts: list[str] = Field(default_factory=list)
    inferences: list[str] = Field(default_factory=list)
    hypotheses: list[str] = Field(default_factory=list)

    def as_text(self) -> str:
        lines: list[str] = []
        for s in self.sprints:
            lines.append(f"{s.id}: {s.name} ({s.time_range[0]} -> {s.time_range[1]})")
            for change in s.architectural_changes:
                lines.append(f"    - {change}")
        return "\n".join(lines)
