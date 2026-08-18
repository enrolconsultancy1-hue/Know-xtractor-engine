"""Data model discovery (conceptual schema, independent of engine)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .common import Confidence, Evidence


class RelationshipKind(str, Enum):
    ONE_TO_ONE = "1:1"
    ONE_TO_MANY = "1:N"
    MANY_TO_MANY = "N:M"


class DataColumn(BaseModel):
    name: str
    type: str = "unknown"
    primary_key: bool = False
    foreign_key: bool = False
    nullable: bool = True
    default: str | None = None


class DataEntity(BaseModel):
    """A conceptual data entity (table / model / collection)."""

    name: str
    kind: str = "table"  # table | model | collection | document
    columns: list[DataColumn] = Field(default_factory=list)
    indexes: list[str] = Field(default_factory=list)
    source_file: str = ""
    source_kind: str = ""  # sqlalchemy | django | pydantic | sql | prisma | other
    confidence: Confidence = Confidence(score=0.7)
    evidence: list[Evidence] = Field(default_factory=list)


class DataRelationship(BaseModel):
    source: str
    target: str
    kind: RelationshipKind = RelationshipKind.ONE_TO_MANY
    via: str = ""


class DataModel(BaseModel):
    """The conceptual data model."""

    entities: list[DataEntity] = Field(default_factory=list)
    relationships: list[DataRelationship] = Field(default_factory=list)
    engines: list[str] = Field(default_factory=list)
