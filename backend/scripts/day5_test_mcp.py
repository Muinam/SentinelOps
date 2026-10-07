import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
 
from app.mcp.client import list_mcp_tools, call_mcp_tool    # Day 5 ka MCP client
 
 
def main():
    # ---- STEP 1: Available tools list karo - confirm karo server connect ho raha hai ----
    print("=" * 60)
    print("Connecting to MCP server aur tools list kar rahe hain...")
    print("=" * 60)
 
    tools = list_mcp_tools()                       # Ye client subprocess me server.py start karega
 
    # Safety check: agar poora "ListToolsResult" object mila (.tools attribute ke sath),
    # to usme se list nikal lo. Agar already plain list hai, to waisa hi rehne do.
    if hasattr(tools, "tools"):                      # hasattr() check karta hai field exist karti hai ya nahi
        tools = tools.tools                            # Object se asal list nikalo
 
    print(f"\nMila: {len(tools)} tools")
    for tool in tools:                               # Har tool ka naam + description print karo
        print(f"  - {tool.name}: {tool.description}")
 
    # ---- STEP 2: Ek tool ko REAL arguments ke sath call karo ----
    # NOTE: container ka naam apna chalta hua container daalein
    # (aapke system pe "airflow-airflow-worker-1" tha, waisa koi naam use karein)
    container_name = "airflow-airflow-worker-1"      # Apna chalta hua container naam yahan daalein
 
    print(f"\nCalling 'docker_check_status' tool for '{container_name}'...")
    result = call_mcp_tool("docker_check_status", {"container_name": container_name})
 
    print("\nMCP Tool Result:")
    print(result)
 
 
if __name__ == "__main__":
    main()