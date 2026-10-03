from app.agents.state import AgentState

# Dummy status-check function (Day 1 se wahi hai)
def _check_system_status(service_name: str) -> dict:
    """Fake status check - Day 4 me ye real Docker se connect hoga."""
    return {
        "service": service_name,
        "status": "unhealthy",
        "cpu_usage": "92%",
        "restart_count_last_hour": 4,
    }

def monitor_node(state: AgentState) -> AgentState:
    """
    LANGGRAPH NODE SIGNATURE: har node ek function hai jo STATE leta hai
    aur UPDATED STATE return karta hai. LangGraph ye updates khud state
    me merge kar deta hai.
    """
    print("[NODE] monitor_node running...")        # Debug ke liye - konsa node chal raha hai dikhane ke liye

    # Error message se service ka naam nikalne ki simple koshish (demo ke liye basic hai)
    service_name = "payment-service" if "payment" in state["error_message"].lower() else "unknown-service"

    status = _check_system_status(service_name)     # Status check karo (no LLM)

    return { "system_status" : status}

    