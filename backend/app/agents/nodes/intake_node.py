from app.agents.state import AgentState                    # State ka shape
from app.db.incidents import open_incident                  # Best-effort incident kholne wala


def intake_node(state: AgentState) -> AgentState:
    print("[NODE] intake_node running...")

    existing = state.get("incident_id")                      # Kya pehle se incident bana hua hai?
    if existing:                                              # Haan - wahi use karo
        print(f"[INTAKE] maujooda incident #{existing} use ho raha hai")
        return {"incident_id": existing}

    incident_id = open_incident(state.get("error_message", ""), state.get("container_name", ""))   # Naya kholo
    if incident_id is None:                                    # Database kharab - graph phir bhi chalega
        print("[INTAKE] ⚠️ incident record nahi bana (DB masla), lekin graph chalta rahega")
    else:
        print(f"[INTAKE] incident #{incident_id} khola gaya")
    return {"incident_id": incident_id}                         # State me ID (ya None)
