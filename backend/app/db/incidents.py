# incidents.py
#
# Is file ka kaam: graph ke liye incident lifecycle ki AASAN, BEST-EFFORT functions.
# Best-effort ka matlab: agar database kharab/band ho to ye sirf WARNING print karta hai
# aur None/khali wapas karta hai - graph ko CRASH nahi karta. (Record rakhna zaroori hai,
# lekin DB down hone par container theek karna nahi rukna chahiye.)

from datetime import datetime, timezone                  # Resolve ka waqt likhne ke liye
from app.db.database import SessionLocal                  # DB session banane ka factory
from app.db import crud                                    # Lifecycle CRUD functions


def open_incident(error_message: str, container_name: str, status: str = "investigating"):
    """
    Naya incident kholta hai aur timeline me pehla event likhta hai.
    status - normal run me "investigating"; watcher "detected" deta hai (worker ke graph chalane tak queue me).
    Return: incident ID (int). DB kharab ho to None.
    """
    try:
        db = SessionLocal()                                  # Naya session
        try:
            incident = crud.create_open_incident(db, error_message, container_name, status)   # Row banao
            crud.add_event(db, incident.id, status, "incident opened")                          # Timeline ka pehla event
            return incident.id                                # ID wapas
        finally:
            db.close()                                         # Session hamesha band
    except Exception as error:                                  # DB band, ya koi aur masla
        print(f"[DB] ⚠️ incident khola nahi ja saka (graph chalta rahega): {error}")
        return None


def set_status(incident_id, status=None, note=None, **fields) -> None:
    """
    Incident ka status aur/ya fields update karta hai, aur status badla ho to timeline me event likhta hai.
    incident_id None ho (DB pehle fail hui thi) to chupchap kuch nahi karta.
    """
    if incident_id is None:                                   # Koi record hai hi nahi
        return
    try:
        if status:                                             # Status badal raha hai
            fields["status"] = status                           # Status bhi update karo
            if status == "resolved":                             # Resolve hua
                fields["resolved_at"] = datetime.now(timezone.utc)   # Waqt likho
            if status == "awaiting_approval":                    # Naye approval ka intezar shuru
                fields.update(approval_decision=None, approved_by=None, approval_note=None, decided_at=None)   # PURANA faisla saaf
        db = SessionLocal()
        try:
            current = crud.get_incident(db, incident_id)              # Abhi ka status dekho
            same_status = bool(status) and current is not None and current.status == status   # Status badla hi nahi?
            crud.update_incident(db, incident_id, **fields)            # Fields update
            if status and not (same_status and not note):              # Asli badlav ho (ya wajah ka note ho) to hi timeline me
                crud.add_event(db, incident_id, status, note)           # Timeline me entry (duplicate shor nahi)
        finally:
            db.close()
    except Exception as error:                                   # Best-effort: crash nahi karna
        print(f"[DB] ⚠️ incident #{incident_id} update nahi hua (graph chalta rahega): {error}")


def count_recent_restarts(container_name: str, hours: int = 1):
    """
    Is container par pichle `hours` ghante me kitni dafa restart shuru hua (policy ki rate limit ke liye).
    Return: int. DB kharab ho to None ("pata nahi" - policy auto-approve band rakhti hai).
    """
    try:
        db = SessionLocal()
        try:
            return crud.count_recent_actions(db, container_name, hours)
        finally:
            db.close()
    except Exception as error:
        print(f"[DB] ⚠️ restart ginti nahi mil saki: {error}")
        return None
