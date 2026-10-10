from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.core.logging import log_node
from app.agents.nodes.monitor_node import monitor_node
from app.agents.nodes.diagnosis_node import diagnosis_node
from app.agents.nodes.solution_node import solution_node
from app.agents.nodes.approval_node import approval_node
from app.agents.nodes.executor_node import executor_node
from app.agents.nodes.rejected_node import rejected_node
from app.agents.nodes.reporter_node import reporter_node

MAX_RETRIES = 2 

def _route_after_approval(state:AgentState) -> str:
    """
    Ye ek ROUTING FUNCTION hai - normal node nahi. Iska kaam sirf STATE
    dekh kar ek STRING return karna hai jo batati hai AGLA node kaunsa ho.
    LangGraph isko "conditional edge" ke sath use karta hai.
    """

    if state.get('approved'):
        return 'executor_step'
    return 'rejected_step'


def _route_after_execution(state: AgentState) -> str:
    """
    Executor ke baad 3 raaste:
      1) Kamyab         -> reporter (incident record karo)
      2) Fail + retries baaki -> diagnosis pe WAPAS (cyclical loop)
      3) Fail + retries khatam -> rejected (manual review)
    """
    if state.get("execution_success"):
        return "reporter_step"
    if state.get("retry_count", 0) <= MAX_RETRIES:
        return "diagnosis_step"                              # LOOP - graph khud ko dobara chalata hai
    return "rejected_step"


def build_graph():
    """
    Graph banata hai aur COMPILE kar ke return karta hai - compiled graph
    hi actually "run" (invoke) ho sakta hai.

    Ab poora flow: monitor -> diagnosis -> solution ->  approval -> (BRANCH)
                                              |-- approved --> reporter -> END
                                              |-- rejected --> rejected -> END
    """

    graph = StateGraph(AgentState)

    graph.add_node("monitor_step", log_node("monitor",monitor_node))
    graph.add_node("diagnosis_step", log_node("diagnosis",diagnosis_node))
    graph.add_node("solution_step", log_node("solution",solution_node))
    graph.add_node('approval_step', log_node("approval",approval_node))
    graph.add_node("executor_step", log_node("executor", executor_node))
    graph.add_node('rejected_step', log_node("rejected",rejected_node))
    graph.add_node("reporter_step", log_node("reporter",reporter_node))

    graph.set_entry_point("monitor_step")

    # ---- Fixed edges ----
    graph.add_edge("monitor_step", "diagnosis_step")
    graph.add_edge("diagnosis_step", "solution_step")
    graph.add_edge("solution_step", "approval_step")

    # ---- Conditional edges (list form - is LangGraph version me dict se zyada reliable) ----
    graph.add_conditional_edges(
        'approval_step', _route_after_approval, ["executor_step", "rejected_step"],
    )

    graph.add_conditional_edges(
        'executor_step', _route_after_execution, 
        ["reporter_step", "diagnosis_step", "rejected_step"]
    )

    graph.add_edge("reporter_step", END)
    graph.add_edge("rejected_step", END)


    return graph.compile()

# Module-level compiled graph
compiled_graph = build_graph()