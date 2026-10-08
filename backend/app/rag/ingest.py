from app.db.database import SessionLocal            # DB session factory
from app.db.crud import get_all_incidents             # Day 6 ka naya CRUD function
from app.tools.rag_tool import remember_incident, memory_size  # Memory me add + disk save


def backfill_from_postgres() -> int:
    """
    Postgres ke saare incidents ko FAISS memory me daalta hai.
    Return: kitne incidents add hue.

    NOTE: Sirf tab chalao jab memory KHALI ho - warna duplicates ban jayenge.
    """
    if memory_size() > 0:                              # Agar memory me pehle se data hai
        print(f"[INGEST] Memory me pehle se {memory_size()} incidents hain - backfill skip")
        return 0

    db = SessionLocal()                                 # Naya DB session
    added = 0
    try:
        incidents = get_all_incidents(db)                 # Postgres se sab incidents
        for inc in incidents:
            # Embed karne ke liye text: error + diagnosis (yehi "meaning" hai incident ki)
            text = f"{inc.error_message} | Diagnosis: {inc.diagnosis}"
            remember_incident(text)                          # Memory me add + disk save
            added += 1
    finally:
        db.close()                                          # Session hamesha band karo

    print(f"[INGEST] Postgres se {added} incidents FAISS memory me add hue")
    return added


if __name__ == "__main__":
    backfill_from_postgres()                               # Seedha chalane par backfill run ho
