from fastapi import APIRouter, Response                           # APIRouter - routes ka group
from sqlalchemy import text                                        # text - raw "SELECT 1" ke liye
from app.db.database import SessionLocal                          # DB session

router = APIRouter(tags=["health"])


@router.get("/health")
def health(response: Response) -> dict:
    """API zinda hai? Database jawab deta hai? DB down ho to 503."""
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))                          # Sab se sasta database check
        finally:
            db.close()
        return {"status": "ok", "database": "ok"}
    except Exception:
        response.status_code = 503                                  # DB nahi mili
        return {"status": "degraded", "database": "error"}