from app.agents.state import AgentState
from app.mcp.client import call_mcp_tool_json

def executor_node(state: AgentState) -> AgentState:
    """
    Restart try karta hai. Kamyab -> verify node agla step hai (wo asal health check karega).
    Fail -> retry_count badhta hai aur review_reason set hota hai.
    """
    print("[NODE] executor_node running...")

    container = state.get("container_name", "")

    result = call_mcp_tool_json("docker_restart", {"container_name": container})   # MCP se restart

    if result.get("restarted"):                           # docker_tool.py "restarted": True/False deta hai
        print(f"✅ Restart call kamyab: {result}")
        return {"execution_success": True, "execution_result": result}

    new_retry_count = state.get("retry_count", 0) + 1     # Fail: ginti badhao
    print(f"❌ Restart fail (attempt {new_retry_count}): {result.get('error')}")
    return {
        "execution_success": False,
        "execution_result": result,
        "retry_count": new_retry_count,
        "reflection_count": 0,                             # Naye cycle me critic ko dobara mauqa mile
        "review_reason": f"Restart failed: {result.get('error')}",
    }

