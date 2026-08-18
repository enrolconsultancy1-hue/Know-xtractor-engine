"""Analysis run endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_session
from app.db.models import AnalysisRun
from app.services.runner import run_state

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.get("/{analysis_id}")
def get_analysis(analysis_id: int, session: Session = Depends(get_session)) -> dict:
    run = session.get(AnalysisRun, analysis_id)
    if not run:
        raise HTTPException(404, "Analysis not found")
    return {
        "id": run.id,
        "project_id": run.project_id,
        "status": run.status,
        "stage": run.stage,
        "progress": run.progress,
        "errors": run.errors,
        "warnings": run.warnings,
        "summary": run.summary,
        "live": run_state(analysis_id),
    }


@router.get("/{analysis_id}/events")
def get_events(analysis_id: int, session: Session = Depends(get_session)) -> dict:
    run = session.get(AnalysisRun, analysis_id)
    if not run:
        raise HTTPException(404, "Analysis not found")
    state = run_state(analysis_id)
    return {"status": run.status, "stage": run.stage, "events": state.get("events", [])}
