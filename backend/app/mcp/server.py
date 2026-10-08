from mcp.server.mcpserver import MCPServer
from app.tools.docker_tool import check_container_status, read_container_logs, restart_container

mcp_server = MCPServer("SentinelOps-Docker-Tools")


@mcp_server.tool()
def docker_check_status(container_name:str):
    """
    Check the live status (running/exited) and image of a Docker container.
    """
    return check_container_status(container_name)

@mcp_server.tool()
def docker_read_logs(container_name:str, tail:int=50):
    """
    Read the most recent logs of a Docker container - useful for diagnosing crashes.
    """
    return read_container_logs(container_name, tail)

@mcp_server.tool()
def docker_restart(container_name:str)-> dict:
    """
    Restart a Docker container. RISKY write action - only call AFTER human approval.
    Database/cache containers (postgres, redis, ...) are protected and will be refused.
    """
    return restart_container(container_name)


if __name__ == "__main__":
    mcp_server.run()
    