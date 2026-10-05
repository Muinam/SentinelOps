from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes.monitor_node import monitor_node
from app.agents.nodes.diagnosis_node import diagnosis_node
from app.agents.nodes.solution_node import solution_node
from app.agents.nodes.approval_node import approval_node
from app.agents.nodes.rejected_node import rejected_node
from app.agents.nodes.reporter_node import reporter_node

def _router_after_approval(state:AgentState) -> str:
    """
    Ye ek ROUTING FUNCTION hai - normal node nahi. Iska kaam sirf STATE
    dekh kar ek STRING return karna hai jo batati hai AGLA node kaunsa ho.
    LangGraph isko "conditional edge" ke sath use karta hai.
    """

    if state.get('approved'):
        return 'reporter_step'
    
    return 'rejected_step'



def build_graph():
    """
    Graph banata hai aur COMPILE kar ke return karta hai - compiled graph
    hi actually "run" (invoke) ho sakta hai.

    Ab poora flow: monitor -> diagnosis -> solution ->  approval -> (BRANCH)
                                              |-- approved --> reporter -> END
                                              |-- rejected --> rejected -> END
    """

    graph = StateGraph(AgentState)

    graph.add_node("monitor_step", monitor_node)
    graph.add_node("diagnosis_step", diagnosis_node)
    graph.add_node("solution_step", solution_node)
    graph.add_node('approval_step',approval_node)
    graph.add_node('rejected_step',rejected_node)
    graph.add_node("reporter_step", reporter_node)

    graph.set_entry_point("monitor_step")

    graph.add_edge("monitor_step", "diagnosis_step")
    graph.add_edge("diagnosis_step", "solution_step")
    graph.add_edge("solution_step", "approval_step")

    graph.add_conditional_edges(
        'approval_step', _router_after_approval,
        ["reporter_step", "rejected_step"],
    )

    graph.add_edge("reporter_step", END)
    graph.add_edge("rejected_step", END)


    return graph.compile()

# Module-level compiled graph
compiled_graph = build_graph()