from app.agents.state import AgentState

def rejected_node(state: AgentState) -> AgentState:
    """Incident ko manual review ke liye mark karta hai aur wajah dikhata hai."""
    print("[NODE] rejected_node running...")

    reason = state.get("review_reason") or "Automatic resolution was not possible."   # Wajah ya default
    print(f"⚠️  Manual review chahiye -> {reason}")
    print(f"    Container: {state.get('container_name')} | Error: {state.get('error_message')}")

    # LangGraph ko har node se kam az kam ek field ka update chahiye - wajah wapas likh dete hain
    return {"review_reason": reason}
