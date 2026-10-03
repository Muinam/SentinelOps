from app.agents.state import AgentState
from app.tools.db_tool import log_incident

def reporter_node(state: AgentState) -> AgentState:
    """
    Poore graph ka data (diagnosis, severity) database me save karta hai.
    Ye graph ka aakhri step hai - is ke baad koi node nahi chalega (END).
    """
    print("[NODE] reporter_node running...")

    result = log_incident(                              # Day 2 ka tool function (seedha call kiya)
        error_message=state["error_message"],
        diagnosis=state["diagnosis"],
        severity=state["severity"],
    )

    print(f"[REPORTER] Incident logged with ID: {result.get('incident_id')}")

    return {"incident_id": result.get("incident_id")}      # State me incident_id save karo