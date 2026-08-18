"""Customization engine: re-bind technologies without disturbing knowledge."""

from __future__ import annotations

from app.domain.architecture import (
    CustomizationRequest,
    ReconstructedArchitecture,
    TechnologyBinding,
)
from app.domain.knowledge import KnowledgePackage


def customize_architecture(pkg: KnowledgePackage, req: CustomizationRequest) -> ReconstructedArchitecture:
    """Apply user technology substitutions to the reconstructed architecture.

    The knowledge model (domain, workflows, components) stays stable; only the
    technology-binding layer changes.
    """
    arch = pkg.reconstructed_architecture or ReconstructedArchitecture()

    bindings: list[TechnologyBinding] = list(arch.technology_bindings)
    for b in bindings:
        if b.concern == "backend-language" and req.backend_technology:
            b.selected = req.backend_technology
            b.rationale = "user-selected backend technology"
        if b.concern == "http-api" and req.backend_technology:
            b.selected = req.backend_technology
            b.rationale = "user-selected backend framework"
        if b.concern == "frontend" and req.frontend_technology:
            b.selected = req.frontend_technology
            b.rationale = "user-selected frontend technology"
        if b.concern == "persistence" and req.database:
            b.selected = req.database
            b.rationale = "user-selected database"

    if req.backend_technology and not any(b.concern in ("backend-language", "http-api") for b in bindings):
        bindings.append(TechnologyBinding(
            concern="http-api", selected=req.backend_technology, rationale="user-selected",
        ))
    if req.frontend_technology and not any(b.concern == "frontend" for b in bindings):
        bindings.append(TechnologyBinding(
            concern="frontend", selected=req.frontend_technology, rationale="user-selected",
        ))
    if req.database and not any(b.concern == "persistence" for b in bindings):
        bindings.append(TechnologyBinding(
            concern="persistence", selected=req.database, rationale="user-selected",
        ))
    if req.deployment_strategy:
        bindings.append(TechnologyBinding(
            concern="deployment", selected=req.deployment_strategy, rationale="user-selected",
        ))
    if req.authentication:
        bindings.append(TechnologyBinding(
            concern="authentication", selected=req.authentication, rationale="user-selected",
        ))

    arch.technology_bindings = bindings
    if req.notes:
        arch.notes = (arch.notes + "\nCustomization notes: " + req.notes).strip()
    return arch
