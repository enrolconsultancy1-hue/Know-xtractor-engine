"""Component discovery models."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field

from .common import Confidence, Evidence


class ComponentType(str, Enum):
    APPLICATION = "application"
    SERVICE = "service"
    MODULE = "module"
    PACKAGE = "package"
    CLASS = "class"
    FUNCTION = "function"
    API_CONTROLLER = "api_controller"
    REPOSITORY = "repository"
    MODEL = "model"
    WORKER = "worker"
    CLI = "cli"
    SCRIPT = "script"
    CONFIGURATION = "configuration"
    MIDDLEWARE = "middleware"
    UNKNOWN = "unknown"


class Component(BaseModel):
    """A discovered architectural component."""

    id: str
    name: str
    type: ComponentType
    purpose: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    dependencies: list[str] = Field(default_factory=list)
    consumers: list[str] = Field(default_factory=list)
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    location: str = ""
    architectural_layer: str = ""
    confidence: Confidence
    evidence: list[Evidence] = Field(default_factory=list)
