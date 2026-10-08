from app.agents.state import AgentState
from app.mcp.client import call_mcp_tool_json

def monitor_node(state: AgentState) -> AgentState:
    """
    Container ka LIVE status aur RECENT logs MCP server se maangta hai,
    aur dono ko state["system_status"] me daal deta hai (diagnosis ke liye).
    """
    print("[NODE] monitor_node running...")        # Debug ke liye - konsa node chal raha hai dikhane ke liye

    container = state.get("container_name","")

    # ---- MCP call 1: status (server alag process me chalta hai, protocol se baat hoti hai) ----
    status = call_mcp_tool_json("docker_check_status", {"container_name": container})

    # ---- MCP call 2: recent logs - logs hi batate hain asal WAJAH ----
    logs_result = call_mcp_tool_json("docker_read_logs", {"container_name": container, "tail": 20})
    logs_text = logs_result.get("logs", logs_result.get("error", ""))   # Logs ya error text

    # Logs lambe ho sakte hain - sirf aakhri 1500 characters rakho (LLM prompt chhota rahe)
    status["recent_logs"] = logs_text[-1500:]

    return {"system_status": status} 
