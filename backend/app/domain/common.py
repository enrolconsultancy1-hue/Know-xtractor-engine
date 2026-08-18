"""Shared primitives: evidence, confidence, and fact classification.

The FACT / INFERENCE / HYPOTHESIS distinction is mandatory across KNOX: every
extracted architectural statement must carry a classification so users (and
downstream agents) can tell observed truth from reasoned guesswork.
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class FactKind(str, Enum):
    """Classification of an extracted statement."""

    FACT = "fact"
    INFERENCE = "inference"
    HYPOTHESIS = "hypothesis"


class Confidence(BaseModel):
    """A confidence score with optional rationale."""

    score: float = Field(ge=0.0, le=1.0, description="0.0 .. 1.0")
    rationale: str = ""

    @property
    def level(self) -> str:
        if self.score >= 0.8:
            return "high"
        if self.score >= 0.5:
            return "medium"
        return "low"


class FileRef(BaseModel):
    """A pointer back into the source repository (evidence, not the source itself)."""

    path: str
    symbol: str | None = None
    line: int | None = None


class Evidence(BaseModel):
    """A concrete piece of evidence backing an extracted fact."""

    file: str
    symbol: str | None = None
    reason: str = ""
    line: int | None = None

    def to_file_ref(self) -> FileRef:
        return FileRef(path=self.file, symbol=self.symbol, line=self.line)
