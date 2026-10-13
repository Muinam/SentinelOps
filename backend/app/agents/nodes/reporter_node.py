from app.agents.state import AgentState
from app.tools.db_tool import log_incident
from app.tools.rag_tool import remember_incident

def reporter_node(state: AgentState) -> AgentState:
    """
    Poore graph ka data (diagnosis, severity) database me save karta hai.
    Ye graph ka aakhri step hai - is ke baad koi node nahi chalega (END).
    """
    print("[NODE] reporter_node running...")

    incident_id = state.get("incident_id")                    # Intake ne jo ID di thi

    # ---- Fallback: DB intake ke waqt fail hua tha ----
    if incident_id is None:
        try:
            result = log_incident(                             # Purane tareeqe se ek row banane ki koshish
                error_message=state["error_message"],
                diagnosis=state["diagnosis"],
                severity=state["severity"],
            )
            incident_id = result.get("incident_id")
            print(f"[REPORTER] fallback se incident #{incident_id} bana")
        except Exception as error:                              # DB ab bhi kharab
            print(f"[REPORTER] ⚠️ Postgres me save nahi hua (graph chalta rahega): {error}")
    else:
        print(f"[REPORTER] incident #{incident_id} resolved mark hoga")

    # ---- FAISS memory me add (solution bhi shamil - agli dafa asli fix mile) ----
    memory_text = (
        f"{state['error_message']} | Diagnosis: {state['diagnosis']} | Fix: {state.get('solution', '')}"
    )
    try:
        remember_incident(memory_text)                          # Embed + index + disk save
        print("[REPORTER] Incident FAISS memory me bhi add ho gaya")
    except Exception as error:
        print(f"[REPORTER] ⚠️ FAISS memory update fail (Postgres record safe hai): {error}")

    return {"incident_id": incident_id}
