import sys                                        
import os                                         
sys.path.append(os.path.join(os.path.dirname(__file__), "..")) 

from app.db.database import Base, engine, SessionLocal   
from app.db.crud import create_incident, get_recent_incidents  


def main():
    # ---- STEP 1: Tables banao (agar pehle se na hon) ----
    # Ye "incidents" table Postgres me create karega agar exist nahi karti
    print("Creating tables (if they don't exist)...")
    Base.metadata.create_all(bind=engine)              # Base se attached saare models ki tables banao

    # ---- STEP 2: Ek session lo aur test incident save karo ----
    db = SessionLocal()

    try:
        print("\nSaving a test incident...")
        incident = create_incident(
            db=db,
            error_message="payment-service crash loop",
            diagnosis="OOM ki wajah se container restart ho raha hai",
            severity="High",
        )
        print(f"  Saved! ID = {incident.id}, created_at = {incident.created_at}")

        # ---- STEP 3: Recent incidents wapas nikalo, confirm karo save hua ----
        print("\nFetching recent incidents...")
        recent = get_recent_incidents(db, limit=5)
        for row in recent:
            print(f"  #{row.id} | {row.severity} | {row.error_message}")

    finally:
        db.close()                                       # Session band karna mat bhoolo


if __name__ == "__main__":
    main()
