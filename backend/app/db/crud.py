from sqlalchemy.orm import Session
from app.db.models import Incident


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