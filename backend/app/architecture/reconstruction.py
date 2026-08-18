"""Architectural reconstruction: technology-neutral design + technology binding."""

from __future__ import annotations

from app.domain.architecture import ReconstructedArchitecture, TechnologyBinding
from app.domain.knowledge import KnowledgePackage


def reconstruct_architecture(pkg: KnowledgePackage) -> ReconstructedArchitecture:
    """Reconstruct the essential architecture, independent of the original source.

    The knowledge layer (domain concepts, capabilities, workflows) is kept
    stable; the technology binding layer maps concerns to concrete tech.
    """
    arch = ReconstructedArchitecture()

    # Essential capabilities from components + workflows.
    capabilities: set[str] = set()
    for wf in pkg.workflows:
        capabilities.add(wf.name)
    for c in pkg.components:
        if c.purpose:
            capabilities.add(c.purpose[:80])

    arch.essential_capabilities = sorted(capabilities)[:40]

    # Domain model from data entities.
    arch.domain_model = [f"{e.name} ({e.kind})" for e in pkg.data_model.entities]

    # Component inventory (technology-neutral roles).
    for c in pkg.components:
        arch.components.append({
            "name": c.name,
            "role": c.type.value,
            "layer": c.architectural_layer,
            "purpose": c.purpose[:120],
        })

    # Architectural requirements.
    arch.architectural_requirements = [
        f"Pattern: {pkg.architecture.primary_pattern or 'layered'}",
        f"API surface: {len(pkg.apis.endpoints)} endpoint(s)" if pkg.apis.endpoints else "No public API",
        f"Data entities: {len(pkg.data_model.entities)}",
        f"Workflows: {len(pkg.workflows)}",
    ]

    # Technology bindings inferred from the detected stack.
    arch.technology_bindings = _infer_bindings(pkg)

    # Data relationships.
    arch.data_relationships = [
        f"{r.source} -> {r.target} ({r.kind.value})" for r in pkg.data_model.relationships
    ]

    # Workflow summaries.
    arch.workflows = [wf.name for wf in pkg.workflows]

    # Constraints and principles.
    arch.constraints = pkg.constraints or ["No constraints extracted"]
    arch.principles = [
        "Separate knowledge (what) from implementation (how)",
        "Keep the domain model independent of technology",
        "Preserve workflows and interfaces across technology changes",
    ]
    arch.notes = (
        "Reconstructed from evidence-backed knowledge. Original source was not copied; "
        "only concepts, relationships, and behavior were retained."
    )
    return arch


def _infer_bindings(pkg: KnowledgePackage) -> list[TechnologyBinding]:
    """Map architectural concerns to detected (or default) technologies."""
    langs = {t.name.lower() for t in pkg.technologies.languages}
    frameworks = {t.name.lower() for t in pkg.technologies.frameworks}
    dbs = {t.name.lower() for t in pkg.technologies.databases}

    def pick(concern: str, candidates: list[str], fallback: str) -> str:
        for c in candidates:
            if c in frameworks or c in langs or c in dbs:
                return c
        return fallback

    bindings: list[TechnologyBinding] = []
    if "python" in langs:
        bindings.append(TechnologyBinding(
            concern="backend-language", original="Python", selected="Python",
            rationale="detected backend language",
        ))
        web = pick("web-framework", ["fastapi", "flask", "django"], "FastAPI")
        bindings.append(TechnologyBinding(concern="http-api", selected=web, rationale="detected framework"))
    elif "javascript" in langs or "typescript" in langs:
        bindings.append(TechnologyBinding(
            concern="backend-language", selected="TypeScript", rationale="detected JS/TS",
        ))
        bindings.append(TechnologyBinding(
            concern="http-api", selected=pick("web-framework", ["express", "next"], "Express"),
            rationale="detected framework",
        ))
    else:
        bindings.append(TechnologyBinding(concern="backend-language", selected="Python", rationale="default"))

    if "react" in frameworks or ".jsx" in str(langs) or "typescript" in langs or "javascript" in langs:
        bindings.append(TechnologyBinding(
            concern="frontend", selected="React + TypeScript", rationale="detected frontend stack",
        ))
    else:
        bindings.append(TechnologyBinding(concern="frontend", selected="React + TypeScript", rationale="default"))

    db = pick("database", ["postgresql", "mysql", "sqlite", "mongodb", "redis"], "SQLite")
    bindings.append(TechnologyBinding(concern="persistence", selected=db, rationale="detected database"))

    return bindings
