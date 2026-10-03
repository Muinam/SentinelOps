from langgraph.graph import StateGraph, END
from app.agents.state import AgentState
from app.agents.nodes.monitor_node import monitor_node
from app.agents.nodes.diagnosis_node import diagnosis_node
from app.agents.nodes.solution_node import solution_node
from app.agents.nodes.reporter_node import reporter_node

def build_graph():
    """
    Graph banata hai aur COMPILE kar ke return karta hai - compiled graph
    hi actually "run" (invoke) ho sakta hai.

    Ab poora flow: monitor -> diagnosis -> solution -> reporter -> END
    """

    graph = StateGraph(AgentState)

    graph.add_node("monitor_step", monitor_node)
    graph.add_node("diagnosis_step", diagnosis_node)
    graph.add_node("solution_step", solution_node)
    graph.add_node("reporter_step", reporter_node)

    graph.set_entry_point("monitor_step")

    graph.add_edge("monitor_step", "diagnosis_step")
    graph.add_edge("diagnosis_step", "solution_step")
    graph.add_edge("solution_step", "reporter_step")
    graph.add_edge("reporter_step", END)


    return graph.compile()

# Module-level compiled graph
compiled_graph = build_graph()