
import sys                                                        # sys - command line argument aur import path
import os                                                         # os - path banane ke liye
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))    # "app" folder import ke liye add karo

from app.db.database import SessionLocal                          # DB session
from app.db.migrate import ensure_schema                          # Schema up-to-date karne ke liye
from app.db import crud                                           # Lifecycle CRUD
from app.db.models import Incident                                # Incident model (list query ke liye)


def show_list(db):
    """Aakhri 10 incidents ki chhoti list."""
    rows = db.query(Incident).order_by(Incident.id.desc()).limit(10).all()   # Naye pehle
    print(f"{'ID':>4}  {'STATUS':<18} {'SEVERITY':<9} {'CONTAINER':<22} ERROR")
    for row in rows:
        print(f"{row.id:>4}  {str(row.status):<18} {str(row.severity or '-'):<9} {str(row.container_name or '-'):<22} {str(row.error_message)[:50]}")


def show_one(db, incident_id):
    """Ek incident ki poori tafseel aur timeline."""
    row = crud.get_incident(db, incident_id)
    if row is None:
        print(f"Incident #{incident_id} nahi mila.")
        return
    print(f"Incident #{row.id}   status: {row.status}")
    print(f"  container    : {row.container_name}")
    print(f"  error        : {row.error_message}")
    print(f"  diagnosis    : {row.diagnosis}")
    print(f"  severity     : {row.severity}   confidence: {row.confidence}")
    print(f"  action       : {row.recommended_action}")
    print(f"  solution     : {row.solution}")
    print(f"  retry_count  : {row.retry_count}")
    print(f"  review_reason: {row.review_reason}")
    print(f"  created/resolved: {row.created_at} / {row.resolved_at}")
    print("\n  TIMELINE:")
    for event in crud.get_events(db, incident_id):
        note = f"  ({event.note})" if event.note else ""
        print(f"    {event.created_at}  {event.status}{note}")


def main():
    ensure_schema()                                                # Purani table me naye columns na hon to jod do
    db = SessionLocal()
    try:
        if len(sys.argv) > 1:                                       # ID di gayi
            show_one(db, int(sys.argv[1]))
        else:
            show_list(db)
    finally:
        db.close()


if __name__ == "__main__":
    main()
