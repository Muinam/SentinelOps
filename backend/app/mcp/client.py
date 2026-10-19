# client.py
#
# Ye hamara MCP CLIENT hai. Ye server.py ko ek SUBPROCESS ki tarah start
# karta hai aur uske sath standard MCP protocol (stdin/stdout ke through
# JSON messages) me baat karta hai.
#
# NOTE: MCP library "async" hai (asyncio). Humne isko "sync wrapper"
# functions me wrap kiya hai, taake baaki project (jo sync hai) easily use kar sake.

import asyncio                                        # Python ka async/await support
import json                                             # json - tool result text ko dict me badalne ke liye
import sys                                              # sys.executable - CURRENT Python interpreter ka exact path
import os                                                # os - working directory path nikalne ke liye
from mcp import ClientSession, StdioServerParameters    # MCP client ke core classes
from mcp.client.stdio import stdio_client                 # stdio (terminal pipe) se connect karne ka helper

# "backend" folder ka absolute path - taake subprocess hamesha sahi jagah se chale
_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---- Server ko kaise START karna hai ----
# "python" ki jagah sys.executable: hamesha EXACT wahi Python (isi venv ka) use hoga
_server_params = StdioServerParameters(
    command=sys.executable,
    args=["-m", "app.mcp.server"],
    cwd=_BACKEND_DIR,
)


async def _list_tools_async() -> list:
    """ASYNC - server se available tools ki list maangta hai."""
    async with stdio_client(_server_params) as (read, write):    # Server subprocess start + pipes
        async with ClientSession(read, write) as session:          # MCP conversation session
            await session.initialize()                               # HANDSHAKE - ye step zaroori hai
            result = await session.list_tools()                       # Tools poocho
            return result.tools                                         # Sirf tools ki list


async def _call_tool_async(tool_name: str, arguments: dict):
    """ASYNC - ek tool ko arguments ke sath call karta hai."""
    async with stdio_client(_server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()                               # HANDSHAKE
            return await session.call_tool(tool_name, arguments)       # Tool call + result


# ---- SYNC wrappers - baaki project ke liye easy interface ----
def list_mcp_tools() -> list:
    """SYNC version - normal function ki tarah call karo."""
    return asyncio.run(_list_tools_async())


def call_mcp_tool(tool_name: str, arguments: dict):
    """SYNC version - raw MCP result object return karta hai."""
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
