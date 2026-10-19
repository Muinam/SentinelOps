# database.py
#
# Is file ka kaam: Postgres se ACTUAL connection banana aur "session"
# provide karna jisse hum queries chala sakein

from sqlalchemy import create_engine                    # Engine - DB ke sath connection pool manage karta hai
from sqlalchemy.orm import sessionmaker, declarative_base  # Session banane aur models define karne ke liye
from app.config import get_settings                      # Hamara config loader

settings = get_settings()                                  # .env se DATABASE_URL uthao

# ---- Engine banao - ye poori app me EK hi baar banega ----
# "engine" DB ke sath low-level connection handle karta hai
engine = create_engine(settings.database_url)               # DATABASE_URL se connect

# ---- SessionLocal - har request/operation ke liye ek naya "session" banane ka factory ----
# autocommit=False, autoflush=False - hum manually control karenge kab data save (commit) ho
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---- Base class - hamare saare models (tables) isi se inherit karenge ----
Base = declarative_base()


def get_db():
    """
    Ye function ek DB session "yield" karta hai aur kaam khatam hone par
    usse automatically band (close) kar deta hai - taake connections leak na hon.
    """
    db = SessionLocal()          # Naya session banao
    try:
        yield db                  # Session ko caller ko de do (use karne ke liye)
    finally:
        db.close()                # Kaam khatam hone par session zaroor band karo
