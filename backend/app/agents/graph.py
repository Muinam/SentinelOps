# graph.py
#
# Is file ka kaam: saare nodes ko ek GRAPH me jodna - "kaunsa node pehle, kaunsa uske baad"
# aur "kab kahan branch/loop karna hai" yahan decide hota hai.
#
# Flow (Day 8: sab se pehle intake - incident ka record kholta hai):
#   intake -> monitor -> diagnosis -> critic -+-> (sabit + fault) -> solution -+-> (restart) -> approval -+-> (haan) -> executor -+-> verify -+-> (healthy) -> reporter -> END
#                  ^                |                                |                         |                       |           |
#                  |  reflection    +-> (sabit nahi) -> diagnosis    +-> (manual) -> rejected  +-> (na) -> rejected     +-> fail   +-> fail
#                  +-- retry loops -+-> (limit khatam / koi fault nahi) -> rejected                                       -> retry ya rejected

from langgraph.graph import StateGraph, END               # StateGraph - graph builder, END - "yahan ruk jao"
from app.agents.state import AgentState
from app.core.logging import log_node                      # Har node ko timing/log ke sath wrap karne ke liye
from app.core.lifecycle import track                       # Day 8: status aur fields database me likhne wala wrapper
from app.agents.nodes.intake_node import intake_node       # Day 8: incident ka record shuru me kholta hai
from app.agents.nodes.monitor_node import monitor_node
from app.agents.nodes.diagnosis_node import diagnosis_node
from app.agents.nodes.critic_node import critic_node        # Naya - Reflection
from app.agents.nodes.solution_node import solution_node
from app.agents.nodes.approval_node import approval_node, external_approval_node   # console aur worker (external) approval
from app.agents.nodes.policy_node import policy_node         # Day 9-11: allowlist/rate-limit/auto-approve ka faisla
from app.agents.nodes.executor_node import executor_node
from app.agents.nodes.verify_node import verify_node        # Naya - restart ke baad health check
from app.agents.nodes.reporter_node import reporter_node
from app.agents.nodes.rejected_node import rejected_node

MAX_RETRIES = 2          # Execution fail hone par pehli koshish ke baad zyada se zyada itni RETRIES
MAX_REFLECTIONS = 1      # Critic diagnosis ko zyada se zyada itni dafa wapas bhej sakta hai
RECURSION_LIMIT = 60     # LangGraph ki default limit 25 hai; hamare loops me worst case usse upar jata hai


def _route_after_critic(state: AgentState) -> str:
    """Critic ke baad: sabit -> solution (ya koi fault nahi to insaan), sabit nahi -> wapas diagnosis ya insaan."""
    if state.get("critic_supported"):                         # Diagnosis evidence se sabit hui
        return "solution_step" if state.get("fault_found") else "rejected_step"   # Fault nahi mila to kuch karna hi nahi
    if state.get("reflection_count", 0) <= MAX_REFLECTIONS:   # Abhi reflection ka mauqa baaki hai
        return "diagnosis_step"                                # Hidayat ke sath dobara diagnose karo
    return "rejected_step"                                     # Mauqe khatam - insaan dekhe


def _route_after_solution(state: AgentState) -> str:
    """Solution ke baad: sirf restart wala action policy tak jata hai, baaki insaan ko."""
    if state.get("recommended_action") == "restart_container":
        return "policy_step"
    return "rejected_step"                                     # manual_intervention


def _route_after_policy(state: AgentState) -> str:
    """Policy ke baad: blocked -> insaan, auto -> seedha executor, human -> approval ka intezar."""
    decision = state.get("policy_decision")
    if decision == "blocked":
        return "rejected_step"
    if decision == "auto":
        return "executor_step"
    return "approval_step"


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


def build_graph(checkpointer=None):
    """
    Graph banata hai aur COMPILE kar ke return karta hai.
    checkpointer=None  -> interactive mode: approval console par input() se (purane scripts/tests).
    checkpointer diya  -> WORKER mode: graph approval_step se PEHLE ruk jata hai (interrupt_before), state
                          checkpointer me save hoti hai, aur faisla DB se aa kar graph resume hota hai.
    """
    graph = StateGraph(AgentState)
    approval_fn = external_approval_node if checkpointer is not None else approval_node   # Kaunsa approval node

    # ---- Nodes (har node log_node() se wrap) - naam state field se alag rakhe ("_step" suffix) ----
    # Har node: log_node (time/log) ke andar track (status + DB sync). Status yahin se dikhta hai.
    graph.add_node("intake_step", log_node("intake", intake_node))                                   # Incident kholta hai
    graph.add_node("monitor_step", log_node("monitor", monitor_node))
    graph.add_node("diagnosis_step", log_node("diagnosis", track(diagnosis_node, before="investigating")))
    graph.add_node("critic_step", log_node("critic", track(critic_node)))
    graph.add_node("solution_step", log_node("solution", track(solution_node)))
    # policy "human" kahe to status awaiting_approval wahin set hota hai (graph approval se pehle ruk bhi sakta hai)
    graph.add_node("policy_step", log_node("policy", track(
        policy_node, after=lambda update: "awaiting_approval" if update.get("policy_decision") == "human" else None)))
    graph.add_node("approval_step", log_node("approval", track(approval_fn)))
    graph.add_node("executor_step", log_node("executor", track(executor_node, before="executing")))
    graph.add_node("verify_step", log_node("verify", track(verify_node, before="verifying")))
    graph.add_node("reporter_step", log_node("reporter", track(reporter_node, after="resolved")))
    graph.add_node("rejected_step", log_node("rejected", track(rejected_node, after="needs_review")))

    graph.set_entry_point("intake_step")

    # ---- Fixed edges ----
    graph.add_edge("intake_step", "monitor_step")                # Day 8: pehle incident kholo
    graph.add_edge("monitor_step", "diagnosis_step")
    graph.add_edge("diagnosis_step", "critic_step")

    # ---- Conditional edges (list form - LangGraph 0.2.45 par verified) ----
    graph.add_conditional_edges("critic_step", _route_after_critic,
                                ["solution_step", "diagnosis_step", "rejected_step"])
    graph.add_conditional_edges("solution_step", _route_after_solution,
                                ["policy_step", "rejected_step"])
    graph.add_conditional_edges("policy_step", _route_after_policy,
                                ["approval_step", "executor_step", "rejected_step"])
    graph.add_conditional_edges("approval_step", _route_after_approval,
                                ["executor_step", "rejected_step"])
    graph.add_conditional_edges("executor_step", _route_after_executor,
                                ["verify_step", "diagnosis_step", "rejected_step"])
    graph.add_conditional_edges("verify_step", _route_after_verify,
                                ["reporter_step", "diagnosis_step", "rejected_step"])

    graph.add_edge("reporter_step", END)
    graph.add_edge("rejected_step", END)

    if checkpointer is None:
        return graph.compile()                                       # Interactive mode
    return graph.compile(checkpointer=checkpointer, interrupt_before=["approval_step"])   # Worker mode: approval se pehle ruko


compiled_graph = build_graph()
