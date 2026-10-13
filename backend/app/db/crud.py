from sqlalchemy.orm import Session
from app.db.models import Incident, IncidentEvent


def create_incident(db:Session, error_message:str, diagnosis:str, severity:str) -> Incident:
    """
    Ek NAYA incident record Postgres me save karta hai.
    """
    incident = Incident(
        error_message=error_message,
        diagnosis=diagnosis,
        severity=severity
    )

    db.add(incident)                                     # Session ko batao "ye record add karna hai"
    db.commit()                                           # Ab ACTUAL DB me save (permanent) karo
    db.refresh(incident)                                  # DB se latest data wapas object me le aao (jaise auto id)
    return incident                                        # Saved incident (with its new ID) return karo


def get_recent_incidents(db: Session, limit: int=5) -> list[Incident]:
    """
    Sab se RECENT incidents nikalta hai (naye se purane order me).
    """

    return (
        db.query(Incident)                                # Incident table pe query shuru
        .order_by(Incident.created_at.desc())               # Sab se naye pehle
        .limit(limit)                                         # Sirf "limit" tak records lo
        .all()                                                  # Query chalao, sab results list me lo
    )

def get_all_incidents(db:Session) -> list[Incident]:
    """
    Day 6 NAYA: Postgres ke SAARE incidents (purane se naye order me) nikalta hai.
    RAG backfill ke liye use hota hai - Postgres ki history ko FAISS memory me daalne ke liye.
    """
    return (
        db.query(Incident)
        .order_by(Incident.created_at.asc())
        .all()
    )


UPDATABLE_FIELDS = {
    "status", "diagnosis", "severity", "solution", "recommended_action", "confidence",
    "retry_count", "review_reason", "resolved_at", "container_name",
}


def create_open_incident(db: Session, error_message: str, container_name: str) -> Incident:
    """Naya incident kholta hai (status: investigating). Diagnosis baad me nodes bharenge."""
    incident = Incident(error_message=error_message, container_name=container_name, status="investigating", retry_count=0)
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
