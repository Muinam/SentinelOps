from typing import Optional                                        # Optional - query parameters ke liye
from fastapi import APIRouter, Depends, HTTPException, Query       # FastAPI ke tools
from sqlalchemy.orm import Session                                  # Session - type hint
from app.api.schemas import (                                       # Request/response shapes
    IncidentCreate, IncidentOut, IncidentDetail, EventOut, DecisionIn, DecisionOut, incident_out,
)
from app.core.guardrails import load_policy, is_allowed, is_protected   # Allowlist aur protected rules
from app.db import crud                                              # Database queries
from app.db.database import get_db                                   # Har request ka DB session

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.get("", response_model=list[IncidentOut])
def list_incidents(
    status: Optional[str] = Query(default=None, description="detected, awaiting_approval, resolved, needs_review..."),
    container: Optional[str] = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Incidents ki list, naye pehle."""
    if status and status not in crud.VALID_STATUSES:                # Unknown status filter
        raise HTTPException(status_code=422, detail=f"status in me se ek hona chahiye: {', '.join(crud.VALID_STATUSES)}")
    return [incident_out(row) for row in crud.list_incidents(db, status, container, limit, offset)]


@router.get("/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: int, db: Session = Depends(get_db)):
    """Ek incident aur uska timeline."""
    row = crud.get_incident(db, incident_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Incident #{incident_id} nahi mila")
    events = [EventOut(status=e.status, note=e.note, created_at=e.created_at) for e in crud.get_events(db, incident_id)]
    return IncidentDetail(**incident_out(row).model_dump(), events=events)


@router.post("", response_model=IncidentOut, status_code=201)
def create_incident(body: IncidentCreate, db: Session = Depends(get_db)):
    """
    Manual trigger: worker ke liye "detected" incident queue me daalta hai.
    Allowlist ke bahar ya protected (database/cache) container par 403; pehle se active incident ho to 409.
    """
    name = body.container_name
    if not is_allowed(name, load_policy()):                          # Allowlist (khali = koi rok nahi, manual runs jaisa)
        raise HTTPException(status_code=403, detail=f"'{name}' allowlist (POLICY_ALLOWED_CONTAINERS) me nahi hai")
    if is_protected(name):                                             # postgres/redis jaise
        raise HTTPException(status_code=403, detail=f"'{name}' protected container hai (database/cache)")
    active = crud.find_active_incident(db, name)                       # Dedupe
    if active is not None:
        raise HTTPException(status_code=409, detail=f"'{name}' ka incident #{active.id} pehle se chal raha hai (status: {active.status})")

    incident = crud.create_open_incident(db, body.error_message, name, status="detected")
    crud.add_event(db, incident.id, "detected", "manual trigger via API")
    return incident_out(incident)


def _decide(incident_id: int, approved: bool, body: DecisionIn, db: Session) -> DecisionOut:
    """approve aur reject ka saanjha kaam."""
    if crud.get_incident(db, incident_id) is None:
        raise HTTPException(status_code=404, detail=f"Incident #{incident_id} nahi mila")
    ok, message = crud.record_decision(db, incident_id, approved, body.by, body.note)
    if not ok:                                                          # Galat status ya pehle se faisla ho chuka
        raise HTTPException(status_code=409, detail=message)
    row = crud.get_incident(db, incident_id)
    return DecisionOut(message=message + " Worker agle round me graph resume karega.", incident=incident_out(row))


@router.post("/{incident_id}/approve", response_model=DecisionOut)
def approve(incident_id: int, body: DecisionIn = DecisionIn(), db: Session = Depends(get_db)):
    """Approval: haan. Sirf awaiting_approval par, aur ek dafa."""
    return _decide(incident_id, True, body, db)


@router.post("/{incident_id}/reject", response_model=DecisionOut)
def reject(incident_id: int, body: DecisionIn = DecisionIn(), db: Session = Depends(get_db)):
    """Approval: na. Sirf awaiting_approval par, aur ek dafa."""
    return _decide(incident_id, False, body, db)
