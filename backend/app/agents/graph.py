from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.core.logging import log_node
from app.agents.nodes.monitor_node import monitor_node
from app.agents.nodes.diagnosis_node import diagnosis_node
from app.agents.nodes.critic_node import critic_node
from app.agents.nodes.solution_node import solution_node
from app.agents.nodes.approval_node import approval_node
from app.agents.nodes.executor_node import executor_node
from app.agents.nodes.verify_node import verify_node
from app.agents.nodes.reporter_node import reporter_node
from app.agents.nodes.rejected_node import rejected_node


MAX_RETRIES = 2          # Execution fail hone par pehli koshish ke baad zyada se zyada itni RETRIES
MAX_REFLECTIONS = 1      # Critic diagnosis ko zyada se zyada itni dafa wapas bhej sakta hai
RECURSION_LIMIT = 60     # LangGraph ki default limit 25 hai; hamare loops me worst case usse upar jata hai

def _route_after_critic(state:AgentState)-> str:
    if state.get("critic_supported"):                         # Diagnosis evidence se sabit hui
        return "solution_step" if state.get("fault_found") else "rejected_step"   # Fault nahi mila to kuch karna hi nahi
    if state.get("reflection_count", 0) <= MAX_REFLECTIONS:   # Abhi reflection ka mauqa baaki hai
        return "diagnosis_step"                                # Hidayat ke sath dobara diagnose karo
    return "rejected_step"


def _route_after_solution(state: AgentState) -> str:
    """Solution ke baad: sirf restart wala action approval tak jata hai, baaki insaan ko."""
    if state.get("recommended_action") == "restart_container":
        return "approval_step"
    return "rejected_step"


def _route_after_approval(state: AgentState) -> str:
    """Insaan ne approve kiya to executor, warna rejected."""
    return "executor_step" if state.get("approved") else "rejected_step"


def _retry_or_reject(state: AgentState) -> str:
    """Execution/verify fail hone par: retries baaki hon to diagnosis pe wapas, warna insaan."""
    if state.get("retry_count", 0) <= MAX_RETRIES:
        return "diagnosis_step"                                # Retry loop
    return "rejected_step"


def _route_after_executor(state: AgentState) -> str:
    """Restart call kamyab -> verify, warna retry/reject."""
    if state.get("execution_success"):
        return "verify_step"
    return _retry_or_reject(state)


def _route_after_verify(state: AgentState) -> str:
    """Container healthy -> reporter, warna retry/reject."""
    if state.get("verified"):
        return "reporter_step"
    return _retry_or_reject(state)


def build_graph():
    """
    Graph banata hai aur COMPILE kar ke return karta hai - compiled graph
    hi actually "run" (invoke) ho sakta hai.

    Ab poora flow: monitor -> diagnosis -> solution ->  approval -> (BRANCH)
                                              |-- approved --> reporter -> END
                                              |-- rejected --> rejected -> END
    """

    graph = StateGraph(AgentState)

    graph.add_node("monitor_step", log_node("monitor", monitor_node))
    graph.add_node("diagnosis_step", log_node("diagnosis", diagnosis_node))
    graph.add_node("critic_step", log_node("critic", critic_node))
    graph.add_node("solution_step", log_node("solution", solution_node))
    graph.add_node("approval_step", log_node("approval", approval_node))
    graph.add_node("executor_step", log_node("executor", executor_node))
    graph.add_node("verify_step", log_node("verify", verify_node))
    graph.add_node("reporter_step", log_node("reporter", reporter_node))
    graph.add_node("rejected_step", log_node("rejected", rejected_node))

    graph.set_entry_point("monitor_step")

    # ---- Fixed edges ----
    graph.add_edge("monitor_step", "diagnosis_step")
    graph.add_edge("diagnosis_step", "critic_step")

    # ---- Conditional edges (list form - LangGraph 0.2.45 par verified) ----
    graph.add_conditional_edges("critic_step", _route_after_critic,
                                ["solution_step", "diagnosis_step", "rejected_step"])
    graph.add_conditional_edges("solution_step", _route_after_solution,
                                ["approval_step", "rejected_step"])
    graph.add_conditional_edges("approval_step", _route_after_approval,
                                ["executor_step", "rejected_step"])
    graph.add_conditional_edges("executor_step", _route_after_executor,
                                ["verify_step", "diagnosis_step", "rejected_step"])
    graph.add_conditional_edges("verify_step", _route_after_verify,
                                ["reporter_step", "diagnosis_step", "rejected_step"])

    graph.add_edge("reporter_step", END)
    graph.add_edge("rejected_step", END)

    return graph.compile()


compiled_graph = build_graph()