# policy_node.py
#
# Graph ka POLICY node: solution ke BAAD aur approval se PEHLE. Core/guardrails.py ke rules lagata hai:
#   blocked -> rejected (wajah ke sath)   auto -> seedha executor   human -> approval ka intezar

from app.agents.state import AgentState                      # State ka shape
from app.core.guardrails import load_policy, evaluate_action  # Rules aur faisla
from app.db.incidents import count_recent_restarts            # Ghante ke restarts (best-effort)


def policy_node(state: AgentState) -> AgentState:
    print("[NODE] policy_node running...")

    container = state.get("container_name", "")                  # Is incident ka container
    decision = evaluate_action(
        policy=load_policy(),
        container=container,
        severity=state.get("severity", ""),
        confidence=state.get("confidence"),
        critic_supported=bool(state.get("critic_supported")),
        action=state.get("recommended_action", ""),
        retry_count=state.get("retry_count", 0),
        recent_restarts=count_recent_restarts(container),           # None = DB masla (auto-approve band, human zaroori)
    )
    print(f"[POLICY] {decision.kind}: {decision.reason}")

    if decision.kind == "blocked":                                # Action nahi hoga
        return {"policy_decision": "blocked", "review_reason": f"Blocked by policy: {decision.reason}"}
    if decision.kind == "auto":                                    # Policy ne khud approve kiya
        return {
            "policy_decision": "auto", "approved": True, "approval_decided": True,
            "approved_by": "auto-policy", "approval_note": decision.reason, "approval_decision": "approved",
        }
    # human: pichla koi faisla (retry se pehle ka) saaf, taake purana "yes" dobara na lag jaye
    return {"policy_decision": "human", "approved": False, "approval_decided": False}
