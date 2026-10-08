from typing import TypedDict

class AgentState(TypedDict):

    error_message: str          # Input - shuru me user/monitor se aata hai
    container_name: str         # kis Docker container pe kaam karna hai
    system_status: dict         # monitor_node isko fill karega
    similar_incidents: list     # diagnosis_node isko fill karega (RAG se)
    diagnosis: str              # diagnosis_node isko fill karega
    severity: str               # diagnosis_node isko fill karega
    solution: str               # solution_node isko fill karega (sham ko banega)
    approved: str               # approval_node isko fill karega (Day 4) - insaan ne haan/na kaha
    execution_success: bool     # executor_node fill karta hai (Day 6) - restart kamyab hua?
    execution_result: dict      # executor_node fill karta hai (Day 6) - restart ka poora result
    retry_count: int            # executor_node badhata hai (Day 6) - kitni dafa fail hua
    incident_id: int            # reporter_node fill karta hai
