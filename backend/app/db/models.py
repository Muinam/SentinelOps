from sqlalchemy import Column, Integer, String, DateTime, Text # Column types
from sqlalchemy.sql import func                                # func.now() - current timestamp ke liye
from app.db.database import Base   

class Incident(Base):
    """
    Ye class ek Postgres TABLE ko represent karti hai.
    Har attribute ek COLUMN hai us table ka.
    """

    __tablename__ = "incidents"          # Actual Postgres table ka naam
    
    id = Column(Integer, primary_key=True, index=True)    # Unique ID - har row ka apna number
    error_message = Column(Text, nullable=False)           # Original error jo aaya tha (empty nahi ho sakta)
    diagnosis = Column(Text, nullable=True)                  # LLM ka diagnosis text (baad me fill hoga)
    severity = Column(String(20), nullable=True)             # "Low" / "Medium" / "High" / "Critical"
    status = Column(String(20), default="open")               # "open" / "resolved" - default "open"
    created_at = Column(DateTime(timezone=True), server_default=func.now())  # Kab record bana - auto-set

