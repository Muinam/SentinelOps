# investigation_tools.py
#
# Is file ka kaam: ReAct investigation ke liye LLM ko dene wale TOOLS banana.
# GUARDRAILS (jaan-boojh kar):
#   1) Sirf READ-ONLY tools - restart jaisa koi write action yahan nahi hai.
#   2) container_name FIXED hai (incident wala container). LLM tool ke arguments me
#      koi aur naam likhe to wo IGNORE hota hai - isse LLM doosre containers ko nahi dekh sakta
#      (logs me chhupi "prompt injection" se bhi bachav hota hai).

from app.mcp.client import call_mcp_tool_json         # MCP ke through Docker se baat karne ka helper
from app.tools.rag_tool import search_similar_incidents  # RAG memory search


def build_investigation_tools(container_name: str):
    """
    Return: (tool_schemas, tool_map)
        tool_schemas - LLM ko dikhane ke liye (naam, description, parameters)
        tool_map     - {naam: python function} - ReAct loop inko chalayega
    """

    # **_ignored - agar LLM koi extra/ghalat argument (jaise container_name) bheje to wo yahan nigal liya jata hai
    def check_status(**_ignored):
        """Container ka live status (running/exited...) - hamesha INCIDENT WALA container."""
        return call_mcp_tool_json("docker_check_status", {"container_name": container_name})

    def read_logs(tail: int = 50, **_ignored):
        """Container ke recent logs - tail 1 se 200 ke beech clamp hota hai."""
        safe_tail = max(1, min(int(tail), 200))             # Kam az kam 1, zyada se zyada 200 lines
        return call_mcp_tool_json("docker_read_logs", {"container_name": container_name, "tail": safe_tail})

    def search_history(query: str = "", **_ignored):
        """Purane similar incidents (RAG memory) me dhoondo."""
        return search_similar_incidents(query or "container incident")   # Query khali ho to ek default query

    tool_schemas = [
        {
            "type": "function",
            "function": {
                "name": "check_status",
                "description": "Get the live status of the incident container (running, exited, restarting...).",
                "parameters": {"type": "object", "properties": {}, "required": []},   # Koi argument nahi
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_logs",
                "description": "Read the most recent log lines of the incident container. Use more lines if the first read is not enough.",
                "parameters": {
                    "type": "object",
                    "properties": {"tail": {"type": "integer", "description": "Number of recent lines, 1 to 200"}},
                    "required": [],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_history",
                "description": "Search past incidents for similar problems and how they were resolved.",
                "parameters": {
                    "type": "object",
                    "properties": {"query": {"type": "string", "description": "Short description of the problem"}},
                    "required": ["query"],
                },
            },
        },
    ]

    tool_map = {"check_status": check_status, "read_logs": read_logs, "search_history": search_history}
    return tool_schemas, tool_map
