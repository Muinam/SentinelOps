from typing import TypedDict

class AgentState(TypedDict):

    error_message: str          # Input - shuru me user/monitor se aata hai
    system_status: dict         # monitor_node isko fill karega
    similar_incidents: list     # diagnosis_node isko fill karega (RAG se)
    diagnosis: str              # diagnosis_node isko fill karega
    severity: str               # diagnosis_node isko fill karega
    solution: str               # solution_node isko fill karega (sham ko banega)
    approved: str               # approval_node isko fill karega (Day 4) - insaan ne haan/na kaha
    incident_id: int            # reporter_node isko fill karega (sham ko banega)
