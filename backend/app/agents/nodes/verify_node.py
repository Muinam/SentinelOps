# verify_node.py
#
# Graph ka VERIFY node (Reflection ka doosra hissa). Restart ke baad container ko kai
# baar check karta hai ke wo sach me healthy hai. "Restart command chali" aur
# "masla theek hua" do alag cheezein hain - ye node doosri wali sabit karta hai.

import time                                              # time - checks ke beech intezar ke liye
from app.agents.state import AgentState                   # State ka shape
from app.mcp.client import call_mcp_tool_json             # MCP se container ka status lene ke liye

VERIFY_CHECKS = 3                                          # Kitni dafa check karna hai
VERIFY_INTERVAL = 3                                        # Har check se pehle kitne second ruknna hai


def verify_node(state: AgentState) -> AgentState:
    """
    Container ko VERIFY_CHECKS baar check karta hai. Har dafa status "running" hona chahiye.
    Ek dafa bhi kuch aur (exited, restarting...) mila to verify fail.
    """
    print("[NODE] verify_node running...")

    container = state.get("container_name", "")            # Kis container ko verify karna hai
    last_status = {}                                         # Aakhri dekha gaya status
    healthy = True                                           # Shuru me maan lo theek hai

    for check in range(1, VERIFY_CHECKS + 1):               # Har check ke liye
        time.sleep(VERIFY_INTERVAL)                           # Container ko sambhalne ka waqt do
        last_status = call_mcp_tool_json("docker_check_status", {"container_name": container})
        print(f"[VERIFY] check {check}/{VERIFY_CHECKS}: status={last_status.get('status')}")
        if last_status.get("status") != "running":           # "running" nahi hai
            healthy = False                                    # Verify fail
            break                                               # Aage check karne ka faida nahi

    if healthy:
        print("✅ Verify kamyab: container stable running hai")
        return {"verified": True}

    new_retry_count = state.get("retry_count", 0) + 1       # Fail hua - retry ginti badhao
    print(f"❌ Verify fail: container healthy nahi mila ({last_status})")
    return {
        "verified": False,
        "execution_success": False,                          # Restart "kamyab" tha lekin masla theek nahi hua
        "retry_count": new_retry_count,
        "reflection_count": 0,                                # Naye cycle me critic ko dobara mauqa mile
        "review_reason": f"Restart ran but the container did not become healthy: {last_status}",
    }
