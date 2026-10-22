# crud.py
#
# CRUD = Create, Read, Update, Delete
# Abhi Day 2 ke liye sirf Create aur Read chahiye - Update/Delete baad me aayenge

from sqlalchemy.orm import Session                 # Type hint ke liye - session ka type
from app.db.models import Incident, IncidentEvent   # Humare table models (Incident Day 2, IncidentEvent Day 8)


def create_incident(db: Session, error_message: str, diagnosis: str, severity: str) -> Incident:
    """
    Ek NAYA incident record Postgres me save karta hai.
    """
    incident = Incident(                              # Naya Python object banao (abhi DB me nahi gaya)
        error_message=error_message,                    # Original error text
        diagnosis=diagnosis,                              # LLM ka diagnosis
        severity=severity,                                 # Severity level
    )
    db.add(incident)                                     # Session ko batao "ye record add karna hai"
    db.commit()                                           # Ab ACTUAL DB me save (permanent) karo
    db.refresh(incident)                                  # DB se latest data wapas object me le aao (jaise auto id)
    return incident                                        # Saved incident (with its new ID) return karo


def get_recent_incidents(db: Session, limit: int = 5) -> list[Incident]:
    """
    Sab se RECENT incidents nikalta hai (naye se purane order me).
    """
    return (
        db.query(Incident)                                # Incident table pe query shuru
        .order_by(Incident.created_at.desc())               # Sab se naye pehle
        .limit(limit)                                         # Sirf "limit" tak records lo
        .all()                                                  # Query chalao, sab results list me lo
    )


def get_all_incidents(db: Session) -> list[Incident]:
    """
    Day 6 NAYA: Postgres ke SAARE incidents (purane se naye order me) nikalta hai.
    RAG backfill ke liye use hota hai - Postgres ki history ko FAISS memory me daalne ke liye.
    """
    return (
        db.query(Incident)                       # Incident table pe query
        .order_by(Incident.created_at.asc())       # Purane pehle (asc = ascending)
        .all()                                      # Sab records list me
    )


# ======================================================================
# Day 8 NAYA: Incident LIFECYCLE ke functions
# ======================================================================

# Sirf yehi columns update ho sakte hain - koi bhi attribute likhne ki ijazat nahi (safety)
UPDATABLE_FIELDS = {
    "status", "diagnosis", "severity", "solution", "recommended_action", "confidence",
    "retry_count", "review_reason", "resolved_at", "container_name",
    "evidence", "approval_decision", "approved_by", "approval_note", "decided_at",   # Day 9-11
}

# Jo statuses "abhi kaam chal raha hai" ka matlab rakhte hain (dedupe aur orphan recovery ke liye)
ACTIVE_STATUSES = ("detected", "investigating", "awaiting_approval", "executing", "verifying")
# Jo statuses "kaam khatam" ka matlab rakhte hain
FINISHED_STATUSES = ("resolved", "needs_review")


def create_open_incident(db: Session, error_message: str, container_name: str, status: str = "investigating") -> Incident:
    """Naya incident kholta hai (default status: investigating; watcher "detected" deta hai). Diagnosis baad me nodes bharenge."""
    incident = Incident(error_message=error_message, container_name=container_name, status=status, retry_count=0)
    db.add(incident)                                      # Session me daalo
    db.commit()                                            # Permanent save
    db.refresh(incident)                                    # Auto id wapas lo
    return incident


def update_incident(db: Session, incident_id: int, **fields) -> "Incident | None":
    """Maujooda incident ke allowed columns update karta hai. Incident na mile to None."""
    incident = db.get(Incident, incident_id)                # Primary key se dhoondo
    if incident is None:                                     # Aisa incident hai hi nahi
        return None
    for name, value in fields.items():                        # Har badlav ke liye
        if name not in UPDATABLE_FIELDS:                       # Allowed list me nahi
            raise ValueError(f"'{name}' update karne ki ijazat nahi")
        setattr(incident, name, value)                          # Value set karo
    db.commit()                                                   # Save
    db.refresh(incident)
    return incident


def add_event(db: Session, incident_id: int, status: str, note: "str | None" = None) -> IncidentEvent:
    """Timeline me ek entry likhta hai: is incident ka status ab ye hua."""
    event = IncidentEvent(incident_id=incident_id, status=status, note=note)
    db.add(event)
    db.commit()
    db.refresh(event)
    return event


def get_incident(db: Session, incident_id: int) -> "Incident | None":
    """Ek incident ID se nikalta hai."""
    return db.get(Incident, incident_id)


def get_events(db: Session, incident_id: int) -> list:
    """Ek incident ka poora timeline (purane se naye)."""
    return (
        db.query(IncidentEvent)
        .filter(IncidentEvent.incident_id == incident_id)       # Sirf is incident ke events
        .order_by(IncidentEvent.id.asc())                         # Hone ke order me
        .all()
    )


def count_incidents(db: Session) -> int:
    """Kul incidents ki ginti (tests aur dashboards ke liye)."""
    return db.query(Incident).count()


# ======================================================================
# Day 9-11 NAYA: approval, watcher, policy aur worker ke queries
# ======================================================================
from datetime import datetime, timedelta, timezone          # Waqt ke hisab kitab ke liye


def as_utc(moment):
    """Database se aaya waqt (SQLite me naive, Postgres me aware) ko UTC aware banata hai - compare ke liye."""
    if moment is None:
        return None
    if moment.tzinfo is None:                                   # Naive hai (SQLite) to UTC maan lo
        return moment.replace(tzinfo=timezone.utc)
    return moment.astimezone(timezone.utc)


def list_by_status(db: Session, status: str, limit: int = 50) -> list:
    """Is status ke incidents, purane pehle (queue ki tarah)."""
    return (
        db.query(Incident)
        .filter(Incident.status == status)
        .order_by(Incident.id.asc())
        .limit(limit)
        .all()
    )


def find_active_incident(db: Session, container_name: str) -> "Incident | None":
    """Is container ka koi incident jo abhi chal raha hai (dedupe ke liye)."""
    return (
        db.query(Incident)
        .filter(Incident.container_name == container_name, Incident.status.in_(ACTIVE_STATUSES))
        .order_by(Incident.id.desc())
        .first()
    )


def in_cooldown(db: Session, container_name: str, cooldown_minutes: int) -> bool:
    """True agar is container ka aakhri incident cooldown_minutes ke andar khatam hua (flapping se bachne ke liye)."""
    last = (
        db.query(Incident)
        .filter(Incident.container_name == container_name, Incident.status.in_(FINISHED_STATUSES))
        .order_by(Incident.id.desc())
        .first()
    )
    if last is None or cooldown_minutes <= 0:                      # Koi purana khatam incident nahi / cooldown band
        return False
    finished_at = as_utc(last.updated_at or last.created_at)       # Kab khatam hua
    return datetime.now(timezone.utc) - finished_at < timedelta(minutes=cooldown_minutes)


def count_recent_actions(db: Session, container_name: str, hours: int = 1) -> int:
    """Is container par pichle `hours` ghanton me kitni dafa restart (executing) shuru hua - rate limit ke liye."""
    since = datetime.now(timezone.utc) - timedelta(hours=hours)
    return (
        db.query(IncidentEvent)
        .join(Incident, Incident.id == IncidentEvent.incident_id)
        .filter(
            Incident.container_name == container_name,
            IncidentEvent.status == "executing",
            IncidentEvent.created_at >= since,
        )
        .count()
    )


def record_decision(db: Session, incident_id: int, approved: bool, by: str, note: "str | None" = None):
    """
    Approval ka faisla likhta hai. Return: (ok, message).
    Sirf tab chalta hai jab incident "awaiting_approval" ho aur abhi tak faisla na hua ho.
    """
    incident = db.get(Incident, incident_id)
    if incident is None:
        return False, f"Incident #{incident_id} nahi mila."
    if incident.status != "awaiting_approval":
        return False, f"Incident #{incident_id} ka status '{incident.status}' hai - approval ka intezar nahi kar raha."
    if incident.approval_decision is not None:
        return False, f"Incident #{incident_id} par faisla ho chuka hai ({incident.approval_decision} by {incident.approved_by})."
    incident.approval_decision = "approved" if approved else "rejected"
    incident.approved_by = by
    incident.approval_note = note
    incident.decided_at = datetime.now(timezone.utc)
    db.commit()
    return True, f"Incident #{incident_id}: {incident.approval_decision} by {by}."


def list_stale_awaiting(db: Session, older_than_minutes: int) -> list:
    """awaiting_approval incidents jin par abhi tak faisla nahi hua aur wo itne minute se zyada purane hain."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=older_than_minutes)
    rows = (
        db.query(Incident)
        .filter(Incident.status == "awaiting_approval", Incident.approval_decision.is_(None))
        .all()
    )
    return [row for row in rows if as_utc(row.updated_at or row.created_at) < cutoff]


VALID_STATUSES = ("open",) + ACTIVE_STATUSES + FINISHED_STATUSES

# API me jo status filter ke taur par maane jaate hain
def list_incidents(db: Session, status: "str | None" = None, container_name: "str | None" = None,
                   limit: int = 50, offset: int = 0) -> list:
    """Incidents ki list, naye pehle. status / container se filter, limit aur offset se pages."""
    query = db.query(Incident)
    if status:                                                # Sirf is status ke
        query = query.filter(Incident.status == status)
    if container_name:                                         # Sirf is container ke
        query = query.filter(Incident.container_name == container_name)
    return query.order_by(Incident.id.desc()).offset(offset).limit(limit).all()

