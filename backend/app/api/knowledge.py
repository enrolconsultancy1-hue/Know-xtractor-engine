"""Knowledge endpoints: navigate the extracted knowledge package."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from app.db import get_session
from app.db.models import Project
from app.knowledge.graph import build_knowledge_graph
from app.services.runner import load_package

router = APIRouter(prefix="/projects/{project_id}", tags=["knowledge"])


def _pkg(project_id: int, session) -> dict:
    if not session.get(Project, project_id):
        raise HTTPException(404, "Project not found")
    pkg = load_package(project_id)
    if not pkg:
        raise HTTPException(409, "No analysis results yet — run an analysis first")
    return pkg


@router.get("/knowledge")
def get_knowledge(project_id: int, session=Depends(get_session)) -> dict:
    return _pkg(project_id, session)


@router.get("/architecture")
def get_architecture(project_id: int, session=Depends(get_session)) -> dict:
    pkg = _pkg(project_id, session)
    return pkg.get("architecture", {})


@router.get("/components")
def get_components(project_id: int, session=Depends(get_session)) -> list:
    pkg = _pkg(project_id, session)
    return pkg.get("components", [])


@router.get("/workflows")
def get_workflows(project_id: int, session=Depends(get_session)) -> list:
    pkg = _pkg(project_id, session)
    return pkg.get("workflows", [])


@router.get("/technologies")
def get_technologies(project_id: int, session=Depends(get_session)) -> dict:
    pkg = _pkg(project_id, session)
    return pkg.get("technologies", {})


@router.get("/sprints")
def get_sprints(project_id: int, session=Depends(get_session)) -> dict:
    pkg = _pkg(project_id, session)
    return pkg.get("architectural_sprints", {})


@router.get("/graph")
def get_graph(project_id: int, session=Depends(get_session)) -> dict:
    from app.domain.knowledge import KnowledgePackage

    pkg = KnowledgePackage.model_validate(_pkg(project_id, session))
    return build_knowledge_graph(pkg)
