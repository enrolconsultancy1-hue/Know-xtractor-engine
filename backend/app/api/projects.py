"""Project endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import AnalysisRun, Project
from app.services.runner import start_analysis

router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectCreate(BaseModel):
    repository_url: str
    name: str | None = None
    branch: str = "main"
    commit_ref: str | None = None


class AnalyzeRequest(BaseModel):
    branch: str = "main"
    commit_ref: str | None = None
    analysis_depth: int = 3


@router.post("", status_code=201)
def create_project(body: ProjectCreate, session: Session = Depends(get_session)) -> dict:
    name = body.name or body.repository_url.rstrip("/").split("/")[-1].removesuffix(".git") or "project"
    project = Project(
        name=name,
        repository_url=body.repository_url,
        branch=body.branch,
        commit_ref=body.commit_ref,
        status="created",
    )
    session.add(project)
    session.commit()
    session.refresh(project)
    return {"id": project.id, "name": project.name, "status": project.status}


@router.get("")
def list_projects(session: Session = Depends(get_session)) -> list[dict]:
    projects = session.scalars(select(Project).order_by(Project.id.desc())).all()
    out = []
    for p in projects:
        last_run = session.scalars(
            select(AnalysisRun).where(AnalysisRun.project_id == p.id).order_by(AnalysisRun.id.desc())
        ).first()
        out.append({
            "id": p.id,
            "name": p.name,
            "repository_url": p.repository_url,
            "status": p.status,
            "last_run_status": last_run.status if last_run else None,
            "summary": last_run.summary if last_run else {},
        })
    return out


@router.get("/{project_id}")
def get_project(project_id: int, session: Session = Depends(get_session)) -> dict:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    runs = session.scalars(
        select(AnalysisRun).where(AnalysisRun.project_id == project_id).order_by(AnalysisRun.id.desc())
    ).all()
    return {
        "id": project.id,
        "name": project.name,
        "repository_url": project.repository_url,
        "branch": project.branch,
        "status": project.status,
        "runs": [
            {"id": r.id, "status": r.status, "summary": r.summary} for r in runs[:10]
        ],
    }


@router.post("/{project_id}/analyze", status_code=202)
def analyze_project(project_id: int, body: AnalyzeRequest, session: Session = Depends(get_session)) -> dict:
    project = session.get(Project, project_id)
    if not project:
        raise HTTPException(404, "Project not found")
    run_id = start_analysis(
        project_id,
        project.repository_url,
        branch=body.branch or project.branch,
        commit_ref=body.commit_ref or project.commit_ref,
    )
    return {"analysis_id": run_id, "status": "started"}


@router.post("/{project_id}/reanalyze", status_code=202)
def reanalyze_project(project_id: int, body: AnalyzeRequest, session: Session = Depends(get_session)) -> dict:
    return analyze_project(project_id, body, session)


@router.post("/{project_id}/cancel")
def cancel_project(project_id: int, session: Session = Depends(get_session)) -> dict:
    from app.services.runner import cancel_analysis

    runs = session.scalars(
        select(AnalysisRun).where(AnalysisRun.project_id == project_id).order_by(AnalysisRun.id.desc())
    ).all()
    for r in runs:
        if r.status in ("running", "pending"):
            cancel_analysis(r.id)
            r.status = "cancelled"
            r.stage = "cancelled"
    session.commit()
    return {"status": "cancelled"}
