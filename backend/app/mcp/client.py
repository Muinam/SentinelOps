import asyncio
import json
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


def call_mcp_tool_json(tool_name: str, arguments: dict) -> dict:
    """
    Day 6 NAYA: tool call kar ke result ko seedha PYTHON DICT me unwrap karta hai.

    MCP result ke andar asal data aisa hota hai: result.content[0].text = '{"status": "running", ...}'
    (JSON string). Hum us string ko json.loads() se dict bana dete hain, taake
    nodes ko MCP ki internal object structure ka pata hi na chale.
    """
    result = call_mcp_tool(tool_name, arguments)             # Raw MCP result
    try:
        text = result.content[0].text                          # Pehle content block ka text
        return json.loads(text)                                  # JSON string -> dict
    except Exception as e:                                        # Agar structure/JSON expected jaisa na ho
        return {"error": f"MCP result parse nahi ho saka: {e}"}