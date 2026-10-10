from app.agents.state import AgentState
from app.tools.db_tool import log_incident
from app.tools.rag_tool import remember_incident

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

    # ---- 2) FAISS memory me bhi add (agli dafa agent isse seekh sake) ----
    # Yahan SOLUTION bhi shamil hai - taake agli baar "similar past fixes" me asal fix mile
    memory_text = (
        f"{state['error_message']} | Diagnosis: {state['diagnosis']} | Fix: {state.get('solution', '')}"
    )

    try:
        remember_incident(memory_text)    
        print("[REPORTER] Incident FAISS memory me bhi add ho gaya")
    
    except Exception as e:
        # Embedding/FAISS fail ho to bhi poora flow na rukay - Postgres me to save ho chuka hai
        print(f"[REPORTER] ⚠️ FAISS memory update fail (Postgres save safe hai): {e}")

    return {"incident_id": result.get("incident_id")}      # State me incident_id save karo