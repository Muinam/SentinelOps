# server.py
#
# Ye hamara MCP SERVER hai. Isko ALAG se chalaya jaata hai (apna process) -
# ye Docker tools ko "serve" karta hai kisi bhi MCP-compatible client ke liye.
#
# IMPORTANT: Ye file DIRECTLY nahi chalani - agent/client isko khud
# "subprocess" ki tarah start kar lega (client.py me dekhenge)

from mcp.server.mcpserver import MCPServer            # NOTE: SDK v2 (July 2026) - "FastMCP" ab "MCPServer" hai
from app.tools.docker_tool import (                    # Docker functions reuse kar rahe hain
    check_container_status,
    read_container_logs,
    restart_container,                                    # Day 6 NAYA - write action (guardrail ke sath)
)

# ---- STEP 1: MCP server object banao - ek naam do ----
mcp_server = MCPServer("SentinelOps-Docker-Tools")       # "SentinelOps-Docker-Tools" = is server ka naam


# ---- STEP 2: Tools ko "@mcp_server.tool()" decorator se REGISTER karo ----
# Ye decorator function ko automatically MCP tool bana deta hai - schema
# (parameters, types) Python type hints se khud generate ho jaata hai!

@mcp_server.tool()
def docker_check_status(container_name: str) -> dict:
    """
    Check the live status (running/exited) and image of a Docker container.
    """
    # Docstring hi is tool ki "description" ban jaati hai MCP clients ke liye
    return check_container_status(container_name)        # Day 4 ka function seedha call kar rahe hain


@mcp_server.tool()
def docker_read_logs(container_name: str, tail: int = 50) -> dict:
    """
    Read the most recent logs of a Docker container - useful for diagnosing crashes.
    """
    return read_container_logs(container_name, tail)       # Day 4 ka function seedha call kar rahe hain


@mcp_server.tool()
def docker_restart(container_name: str) -> dict:
    """
    Restart a Docker container. RISKY write action - only call AFTER human approval.
    Database/cache containers (postgres, redis, ...) are protected and will be refused.
    """
    return restart_container(container_name)                 # Guardrail docker_tool.py ke andar hi hai


# ---- STEP 3: Server ko RUN karo (jab ye file directly chalayi jaye) ----
if __name__ == "__main__":
    mcp_server.run()                                          # Server start - stdin/stdout pe listen karega
