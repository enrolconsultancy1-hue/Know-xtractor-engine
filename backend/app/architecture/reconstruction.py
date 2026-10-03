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
    import re

    langs = {t.name.lower() for t in pkg.technologies.languages}
    frameworks = {t.name.lower() for t in pkg.technologies.frameworks}
    dbs = {t.name.lower() for t in pkg.technologies.databases}
    deps = {d.name.lower() for d in pkg.technologies.dependencies}

    # Determine dominant language by file counts in rationale
    def _file_count(lang_obj) -> int:
        rationale = getattr(getattr(lang_obj, "confidence", None), "rationale", "") or ""
        m = re.search(r"(\d+)\s+file", rationale)
        return int(m.group(1)) if m else 1

    sorted_langs = sorted(pkg.technologies.languages, key=_file_count, reverse=True)
    primary_lang = sorted_langs[0].name.lower() if sorted_langs else "python"

    def pick(concern: str, candidates: list[str], fallback: str) -> str:
        for c in candidates:
            if c in frameworks or c in langs or c in dbs or c in deps:
                return c
        return fallback

    bindings: list[TechnologyBinding] = []
    if primary_lang in ("javascript", "typescript") or (primary_lang not in ("python", "go", "rust", "java") and ("javascript" in langs or "typescript" in langs)):
        bindings.append(TechnologyBinding(
            concern="backend-language", original=sorted_langs[0].name if sorted_langs else "JavaScript",
            selected="TypeScript / JavaScript (Node.js)", rationale=f"dominant language ({sorted_langs[0].name if sorted_langs else 'JS'})",
        ))
        web = "Vite Dev Server / Express Middleware" if "vite" in frameworks or "vite" in deps or any("vite" in ep for ep in pkg.architecture.entry_points) else pick("web-framework", ["express", "next", "koa"], "Express")
        bindings.append(TechnologyBinding(concern="http-api", selected=web, rationale="detected framework"))
    elif primary_lang == "python" or "python" in langs:
        bindings.append(TechnologyBinding(
            concern="backend-language", original="Python", selected="Python",
            rationale="detected backend language",
        ))
        web = pick("web-framework", ["fastapi", "flask", "django"], "FastAPI")
        bindings.append(TechnologyBinding(concern="http-api", selected=web, rationale="detected framework"))
    else:
        bindings.append(TechnologyBinding(concern="backend-language", selected="Python", rationale="default"))
        bindings.append(TechnologyBinding(concern="http-api", selected="FastAPI", rationale="default"))

    # Frontend / 3D Graphics Engine
    if any("cesium" in d for d in deps):
        bindings.append(TechnologyBinding(
            concern="3d-geospatial-engine", selected="CesiumJS (3D WebGL / WGS84 Globe)",
            rationale="detected Cesium 3D geospatial dependency",
        ))
    elif any("three" in d for d in deps):
        bindings.append(TechnologyBinding(
            concern="3d-rendering-engine", selected="Three.js (WebGL)",
            rationale="detected Three.js dependency",
        ))

    if "react" in frameworks or any("react" in d for d in deps):
        bindings.append(TechnologyBinding(
            concern="frontend", selected="React + TypeScript", rationale="detected React stack",
        ))
    elif "javascript" in langs or "typescript" in langs:
        bindings.append(TechnologyBinding(
            concern="frontend", selected="Modern Web / ES Modules + HTML5", rationale="detected JS/TS frontend stack",
        ))
    else:
        bindings.append(TechnologyBinding(concern="frontend", selected="React + TypeScript", rationale="default"))

    # Database & Cache
    if "redis" in dbs or any("redis" in d for d in deps):
        bindings.append(TechnologyBinding(concern="persistence", selected="Redis (In-Memory Key-Value & Geospatial Store)", rationale="detected Redis database/cache"))
    else:
        db = pick("database", ["postgresql", "mysql", "sqlite", "mongodb"], "SQLite / In-Memory Store")
        bindings.append(TechnologyBinding(concern="persistence", selected=db, rationale="detected persistence"))

    return bindings
