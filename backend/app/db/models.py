# models.py
#
# Is file ka kaam: Postgres tables ki STRUCTURE Python classes ki tarah define karna (ORM models).
# Day 8: Incident ab poora LIFECYCLE rakhta hai (detect hone se resolve/review tak),
# aur IncidentEvent har status badlav ka timeline (audit trail).

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, ForeignKey   # Column ke types
from sqlalchemy.sql import func                                  # func.now() - current timestamp ke liye
from app.db.database import Base                                  # Base class jo database.py me banayi


class Incident(Base):
    """
    Ek incident ki poori kahani. status in values me se ek hota hai:
      investigating     - graph ne incident khola, diagnose ho raha hai
      awaiting_approval - insaan ke faisle ka intezar
      executing         - restart chal raha hai
      verifying         - restart ke baad health check
      resolved          - container theek hua
      needs_review      - automatic raasta khatam, insaan dekhe (wajah review_reason me)
      detected          - watcher ne masla pakda, worker ke graph chalane ka intezar (queue)
      open              - purane (Day 2-7) test records
    """

    __tablename__ = "incidents"                                   # Actual Postgres table ka naam

    # ---- Purane columns (Day 2) - inko mat badlein ----
    id = Column(Integer, primary_key=True, index=True)             # Unique ID
    error_message = Column(Text, nullable=False)                    # Jo error aaya tha
    diagnosis = Column(Text, nullable=True)                          # Root cause
    severity = Column(String(20), nullable=True)                      # Low / Medium / High / Critical
    status = Column(String(20), default="open")                        # Lifecycle ka status (upar dekhein)
    created_at = Column(DateTime(timezone=True), server_default=func.now())   # Kab bana

    # ---- Naye columns (Day 8) ----
    container_name = Column(String(200), nullable=True)               # Kis container ka incident hai
    solution = Column(Text, nullable=True)                              # Solution ki wazahat
    recommended_action = Column(String(40), nullable=True)               # restart_container / manual_intervention
    confidence = Column(Float, nullable=True)                             # Diagnosis par bharosa (0.0 - 1.0)
    retry_count = Column(Integer, default=0)                               # Kitni dafa execution fail hua
    review_reason = Column(Text, nullable=True)                             # Insaan ke paas kyun gaya
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())  # Aakhri badlav
    resolved_at = Column(DateTime(timezone=True), nullable=True)             # Kab resolve hua

    # ---- Naye columns (Day 9-11): approval aur evidence ----
    evidence = Column(Text, nullable=True)                                      # Diagnosis ke evidence quotes (JSON list)
    approval_decision = Column(String(10), nullable=True)                        # "approved" / "rejected" / None (abhi faisla nahi hua)
    approved_by = Column(String(100), nullable=True)                              # Kis ne faisla kiya (naam, ya "auto-policy"/"system")
    approval_note = Column(Text, nullable=True)                                    # Faisle ke sath chhota note
    decided_at = Column(DateTime(timezone=True), nullable=True)                     # Faisla kab hua


class IncidentEvent(Base):
    """Har status badlav ka ek record - incident ka TIMELINE (kab kya hua)."""

    __tablename__ = "incident_events"                              # Naya table (create_all khud bana deta hai)

    id = Column(Integer, primary_key=True, index=True)               # Unique ID
    incident_id = Column(Integer, ForeignKey("incidents.id"), index=True, nullable=False)   # Kis incident ka event
    status = Column(String(20), nullable=False)                        # Naya status
    note = Column(Text, nullable=True)                                  # Chhoti wazahat (jaise review_reason)
    created_at = Column(DateTime(timezone=True), server_default=func.now())   # Kab hua
