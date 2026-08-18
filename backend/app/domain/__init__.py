"""Domain package: the strongly-typed Pydantic knowledge model."""

from .api_model import ApiEndpoint, ApiSpec
from .architecture import (
    ArchitectureLayer,
    ArchitecturePattern,
    ArchitectureReport,
    CustomizationRequest,
    ReconstructedArchitecture,
)
from .common import Confidence, Evidence, FactKind, FileRef
from .component import Component, ComponentType
from .data_model import DataColumn, DataEntity, DataModel, RelationshipKind
from .implementation import ImplementationSpec
from .knowledge import KnowledgePackage
from .sprint import ArchitecturalSprint, CommitInfo, EvolutionTimeline
from .technology import DependencyInfo, Technology, TechnologyStack
from .workflow import Workflow, WorkflowNode, WorkflowStep

__all__ = [
    "ApiEndpoint",
    "ApiSpec",
    "ArchitectureLayer",
    "ArchitecturePattern",
    "ArchitectureReport",
    "ArchitecturalSprint",
    "CommitInfo",
    "Component",
    "ComponentType",
    "Confidence",
    "CustomizationRequest",
    "DataColumn",
    "DataEntity",
    "DataModel",
    "DependencyInfo",
    "Evidence",
    "EvolutionTimeline",
    "FactKind",
    "FileRef",
    "ImplementationSpec",
    "KnowledgePackage",
    "ReconstructedArchitecture",
    "RelationshipKind",
    "Technology",
    "TechnologyStack",
    "Workflow",
    "WorkflowNode",
    "WorkflowStep",
]
