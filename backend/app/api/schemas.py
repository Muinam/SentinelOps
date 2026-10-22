import json                                                       # json - evidence text ko list banane ke liye
from datetime import datetime                                     # datetime - waqt ke fields
from typing import Optional                                       # Optional - "ho bhi sakta hai, nahi bhi"
from pydantic import BaseModel, Field                              # BaseModel - schema, Field - limits

# Docker container ke legal naam jaisa: pehla akshar/number, phir akshar, number, _, ., -
CONTAINER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9_.-]*$"


class IncidentCreate(BaseModel):
    """Manual trigger: kis container par kya masla hai."""
    container_name: str = Field(min_length=1, max_length=200, pattern=CONTAINER_PATTERN)
    error_message: str = Field(min_length=5, max_length=1000)


class DecisionIn(BaseModel):
    """Approve/reject ke sath: kis ne kiya aur note."""
    by: str = Field(default="api", min_length=1, max_length=100)
    note: Optional[str] = Field(default=None, max_length=500)


class EventOut(BaseModel):
    """Timeline ki ek entry."""
    status: str
    note: Optional[str] = None
    created_at: Optional[datetime] = None


class IncidentOut(BaseModel):
    """Ek incident ka jawab."""
    id: int
    status: Optional[str] = None
    container_name: Optional[str] = None
    error_message: str
    diagnosis: Optional[str] = None
    severity: Optional[str] = None
    confidence: Optional[float] = None
    recommended_action: Optional[str] = None
    solution: Optional[str] = None
    evidence: list[str] = Field(default_factory=list)
    retry_count: Optional[int] = None
    review_reason: Optional[str] = None
    approval_decision: Optional[str] = None
    approved_by: Optional[str] = None
    approval_note: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    decided_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None


class IncidentDetail(IncidentOut):
    """Incident + uska poora timeline."""
    events: list[EventOut] = Field(default_factory=list)


class DecisionOut(BaseModel):
    """Approve/reject ka nateeja."""
    message: str
    incident: IncidentOut


def _evidence_list(raw) -> list:
    """Database me evidence JSON text hota hai - isko list banata hai (kharab ho to khali list)."""
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return [str(item) for item in value] if isinstance(value, list) else [str(value)]
    except (ValueError, TypeError):
        return [str(raw)]


def incident_out(row) -> IncidentOut:
    """Database row (Incident) ko API ke jawab me badalta hai."""
    return IncidentOut(
        id=row.id, status=row.status, container_name=row.container_name, error_message=row.error_message,
        diagnosis=row.diagnosis, severity=row.severity, confidence=row.confidence,
        recommended_action=row.recommended_action, solution=row.solution, evidence=_evidence_list(row.evidence),
        retry_count=row.retry_count, review_reason=row.review_reason, approval_decision=row.approval_decision,
        approved_by=row.approved_by, approval_note=row.approval_note, created_at=row.created_at,
        updated_at=row.updated_at, decided_at=row.decided_at, resolved_at=row.resolved_at,
    )
