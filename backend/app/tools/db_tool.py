from app.db.database import SessionLocal
from app.db.crud import create_incident  # Database function jo record save karta hai

def log_incident(error_message:str, diagnosis:str, severity:str) -> dict:
    """
    YE FUNCTION LLM call karega jab uska diagnosis complete ho jaye,
    taake record permanently Postgres me store ho jaye (audit trail).
    """
    
    db = SessionLocal() # all diagnosis complete hona ka db ma save ho ga
    try:
        incident = create_incident(
            db=db,
            error_message=error_message,
            diagnosis=diagnosis,
            severity=severity
        )
        return { 
            "status": "logged",
            "incident_id": incident.id # Success response LLM ko
        }
    finally:
        db.close()    # Session hamesha band karo, chahe error aaye


# ---- Tool ka SCHEMA (Groq/OpenAI-style) ----
DB_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "log_incident",
        "description": (
            "Save the diagnosed incident to the database for record-keeping. "
            "Call this AFTER you have completed your diagnosis, not before."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "error_message": {"type": "string", "description": "The original error message"},
                "diagnosis": {"type": "string", "description": "Your diagnosis summary"},
                "severity": {
                    "type": "string",
                    "enum": ["Low", "Medium", "High", "Critical"],   # Sirf ye 4 values allowed
                    "description": "Severity level of the incident",
                },
            },
            "required": ["error_message", "diagnosis", "severity"],
        },
    },
}
