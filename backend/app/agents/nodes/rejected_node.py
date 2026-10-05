from app.agents.state import AgentState

def rejected_node(state: AgentState) -> AgentState:
    """
    Rejection ko record karta hai - abhi sirf print kar raha hai,
    future me isko bhi Postgres me "status: rejected" ke sath save kar sakte hain.
    """
    print("[NODE] rejected_node running...")
    print(f"⚠️  Incident NOT auto-resolved - manual review chahiye: {state['error_message']}")

    return {'approved': False}
