"""Architecture customization + implementation prompt + export endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import Project
from app.domain.architecture import CustomizationRequest
from app.domain.knowledge import KnowledgePackage
from app.services.exporter import to_json, to_markdown, to_yaml
from app.services.runner import load_package

router = APIRouter(prefix="/projects/{project_id}", tags=["architecture"])


def _load_pkg(project_id: int, session: Session) -> KnowledgePackage:
    if not session.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    data = load_package(project_id)
    if not data:
        raise HTTPException(409, "No analysis results yet — run an analysis first")
    return KnowledgePackage.model_validate(data)


@router.post("/architecture/customize")
def customize(project_id: int, req: CustomizationRequest, session: Session = Depends(get_session)) -> dict:
    pkg = _load_pkg(project_id, session)
    from app.architecture.customization import customize_architecture
    from app.services.knowledge_extractor import build_implementation_spec

    new_arch = customize_architecture(pkg, req)
    pkg.reconstructed_architecture = new_arch
    pkg.implementation_specification = build_implementation_spec(pkg)

    # Persist updated package.
    from app.services.runner import package_path

    package_path(project_id).write_text(pkg.model_dump_json(indent=2), encoding="utf-8")
    return {
        "reconstructed_architecture": new_arch.model_dump(mode="json"),
        "implementation_specification": pkg.implementation_specification.model_dump(mode="json"),
    }


@router.post("/implementation-prompt")
def implementation_prompt(project_id: int, req: CustomizationRequest | None = None,
                          session: Session = Depends(get_session)) -> dict:
    pkg = _load_pkg(project_id, session)
    if req:
        from app.architecture.customization import customize_architecture
        from app.services.knowledge_extractor import build_implementation_spec

        pkg.reconstructed_architecture = customize_architecture(pkg, req)
        pkg.implementation_specification = build_implementation_spec(pkg)

    spec = pkg.implementation_specification
    project_name = pkg.metadata.get("repository", "project")
    prompt = spec.to_prompt(project_name)
    return {
        "project": project_name,
        "prompt": prompt,
        "technology_stack": spec.technology_stack,
        "implementation_order": spec.implementation_order,
    }


@router.post("/export")
def export(project_id: int, fmt: str = "markdown", session: Session = Depends(get_session)) -> dict:
    pkg = _load_pkg(project_id, session)
    if fmt == "json":
        content = to_json(pkg)
        media_type = "application/json"
    elif fmt in ("yaml", "yml"):
        content = to_yaml(pkg)
        media_type = "application/yaml"
    else:
        content = to_markdown(pkg)
        media_type = "text/markdown"
    return {"format": fmt, "content": content, "media_type": media_type}
