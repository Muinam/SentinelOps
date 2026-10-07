import asyncio
import sys
import os
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

# "backend" folder ka absolute path - taake subprocess hamesha sahi jagah se chale
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

_server_params = StdioServerParameters(
    command=sys.executable,
    args=['-m', 'app.mcp.server'],
    cwd=_BACKEND_DIR,
)

async def _list_tool_async():
    """
    ASYNC function - server se "available tools" ki list maangta hai.
    """
    async with stdio_client(_server_params) as (read, write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            result = await session.list_tools()
            return result

async def _call_tool_async(tool_name:str, arguments:dict) -> dict:
    async with stdio_client(_server_params) as (read, write):
        async with ClientSession(read,write) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments)
            return result


# ---- STEP 2: SYNC wrapper functions - baaki project (sync) ke liye easy interface ----
def list_mcp_tools():
    """
    SYNC version - poore project me isko normal function ki tarah call kar sakte hain,
    "async/await" ki zaroorat nahi padegi.
    """
    return asyncio.run(_list_tool_async())


def call_mcp_tool(tool_name:str, arguments:dict) -> dict:
    """
    SYNC version - MCP tool ko call karne ka simple interface.
    """
    return asyncio.run(_call_tool_async(tool_name, arguments)) 