from docker.api import container
from app.agents.state import AgentState
from app.mcp.client import call_mcp_tool_json

def executor_node(state: AgentState) -> AgentState:
    """
    Restart try karta hai aur nateeja state me likhta hai.
    Kamyab -> execution_success=True. Fail -> execution_success=False aur retry_count +1.
    """
    print("[NODE] executor_node running...")

    container = state.get('container_name','')

    result = call_mcp_tool_json("docker_restart",{'container_name':container})

    success = bool(result.get('restarted'))

    if success:
        print(f"✅ Restart kamyab: {result}")
        return {"execution_success": True, "execution_result": result}

    # ---- Fail hua: retry_count badhao taake graph ko pata chale kitni dafa fail hua ----
    new_retry_count = state.get("retry_count", 0) + 1
    print(f"❌ Restart fail (attempt {new_retry_count}): {result.get('error')}")
    return {
        "execution_success": False,
        "execution_result": result,
        "retry_count": new_retry_count,
    }

