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


@router.get("/{analysis_id}/stream")
async def stream_analysis(analysis_id: int, session: Session = Depends(get_session)):
    """Server-Sent Events (SSE) streaming endpoint for live analysis progress."""
    import asyncio
    import json

    from fastapi.responses import StreamingResponse

    from app.db import SessionLocal

    run = session.get(AnalysisRun, analysis_id)
    if not run:
        raise HTTPException(404, "Analysis not found")

    async def event_generator():
        last_event_count = 0
        try:
            while True:
                live = run_state(analysis_id)
                status = live.get("status", "unknown")
                stage = live.get("stage", "")
                progress = live.get("progress", 0.0)
                events = live.get("events", [])

                if status == "unknown":
                    db_fresh = SessionLocal()
                    try:
                        r = db_fresh.get(AnalysisRun, analysis_id)
                        if r:
                            status = r.status
                            stage = r.stage or ""
                            progress = float(r.progress or 0.0)
                    finally:
                        db_fresh.close()

                # Emit new events if any
                if len(events) > last_event_count:
                    for ev in events[last_event_count:]:
                        payload = {
                            "id": analysis_id,
                            "status": status,
                            "stage": ev.get("stage", stage),
                            "progress": ev.get("pct", progress),
                            "message": ev.get("message", ""),
                        }
                        yield f"event: progress\ndata: {json.dumps(payload)}\n\n"
                    last_event_count = len(events)
                else:
                    payload = {
                        "id": analysis_id,
                        "status": status,
                        "stage": stage,
                        "progress": progress,
                    }
                    yield f"event: status\ndata: {json.dumps(payload)}\n\n"

                if status in ("done", "failed", "cancelled"):
                    complete_payload = {
                        "id": analysis_id,
                        "status": status,
                        "stage": stage,
                        "progress": progress,
                        "summary": live.get("summary", {}),
                        "errors": live.get("errors", []),
                    }
                    yield f"event: done\ndata: {json.dumps(complete_payload)}\n\n"
                    break

                await asyncio.sleep(0.5)
        except (asyncio.CancelledError, GeneratorExit):
            return

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

