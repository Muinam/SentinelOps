from typing import TypedDict

class AgentState(TypedDict):
    """
    Poore graph ki "notebook" ka structure. Neeche comment me likha hai KAUNSA node fill karta hai.
    """

    # ---- Input ----
    error_message: str            # Shuru me user/watcher se aata hai
    container_name: str           # Kis Docker container pe kaam karna hai

    # ---- monitor_node ----
    system_status: dict           # Real Docker status + recent logs (MCP se)

    # ---- diagnosis_node (ReAct + structured JSON) ----
    similar_incidents: list       # RAG se mile purane incidents
    react_trace: list             # ReAct ke har step ka record (tool, args, observation)
    fault_found: bool             # Kya evidence me asal fault hai?
    diagnosis: str                # Root cause (text)
    severity: str                 # Low / Medium / High / Critical (validated)
    diagnosis_evidence: list      # Status/logs se hu-ba-hu quotes
    confidence: float             # 0.0 se 1.0
    diagnosis_failed: bool        # LLM valid JSON nahi de paya

    # ---- critic_node (Reflection) ----
    critic_supported: bool        # Critic ne diagnosis ko evidence se sabit maana?
    critic_feedback: str          # Diagnosis agent ke liye hidayat (reflection loop me use hoti hai)
    reflection_count: int         # Critic ne kitni dafa diagnosis wapas bheja

    # ---- solution_node (structured) ----
    solution: str                 # Solution ki wazahat
    recommended_action: str       # "restart_container" ya "manual_intervention"

    # ---- approval_node ----
    approved: bool                # Insaan ne haan/na kaha

    # ---- executor_node aur verify_node ----
    execution_success: bool       # Restart (aur verify) kamyab hua?
    execution_result: dict        # Restart ka poora result
    verified: bool                # Restart ke baad container sach me healthy mila?
    retry_count: int              # Kitni dafa execution fail hua

    # ---- Aakhri nateeja ----
    review_reason: str            # Incident insaan ko kyun bheja gaya (kisi bhi node se set hota hai)
    incident_id: int              # reporter_node fill karta hai
