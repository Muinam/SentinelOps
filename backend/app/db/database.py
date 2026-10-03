from sqlalchemy import create_engine                        # Engine - DB ke sath connection pool manage karta hai
from sqlalchemy.orm import sessionmaker, declarative_base   # Session banane aur models define karne ke liye
from app.config import get_settings

settings = get_settings()

# ---- Engine banao - ye poori app me EK hi baar banega ----
# "engine" DB ke sath low-level connection handle karta hai
engine = create_engine(settings.database_url)       # DATABASE_URL se connect


# ---- SessionLocal - har request/operation ke liye ek naya "session" banane ka factory ----
# autocommit=False, autoflush=False - hum manually control karenge kab data save (commit) ho
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ---- Base - ye saare models ka parent hai ----
Base = declarative_base()

def get_db():
    """
    Ye function ek DB session "yield" karta hai aur kaam khatam hone par
    usse automatically band (close) kar deta hai - taake connections leak na hon.
    """
    db = SessionLocal() # Naya Session banao
    try:
        yield db      # Session ko FastAPI router tak pahunchao
    finally:
        db.close()    # Kaam khatam → Session band