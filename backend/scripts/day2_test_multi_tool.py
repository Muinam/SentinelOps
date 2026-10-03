from concurrent.futures.process import _check_system_limits
import sys
import os 
import json

sys.path.append(os.path.join(os.path.dirname(__file__),".."))

from app.llm.client import call_llm
from app.agents.prompts.diagnosis_prompt import DIAGNOSIS_SYSTEM_PROMPT
from app.tools.rag_tool import search_similar_incidents, seed_incident_history, RAG_TOOL_SCHEMA

def check_system_status(service_name:str) ->dict:
    """Dummy function - Day 1 wali hi hai, abhi fake data deta hai."""
    return {
        "service": service_name,
        "status": "unhealthy",
        "cpu_usage": "92%",
        "restart_count_last_hour": 4,
    }

SYSTEM_STATUS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "check_system_status",
        "description": (
            "Check the live health status, CPU usage, and recent restart count "
            "of a given service/container."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {"type": "string", "description": "Name of the service"}
            },
            "required": ["service_name"],
        },
    },
}

all_tools = [SYSTEM_STATUS_TOOL_SCHEMA, RAG_TOOL_SCHEMA]

# Python function name -> actual function ka mapping (tool call aane par isse dhoondenge)
tool_function_map = {
    "check_system_status": check_system_status,
    "search_similar_incidents": search_similar_incidents,
}


def run_diagnosis(error_message: str) -> str:
    """
    Ab ye loop MULTIPLE tool calls handle karta hai - agar LLM ek call me
    do tools bhi maang le (jaise: pehle RAG check karo, phir status check karo),
    to hum sab ko loop me process karenge.
    """

    messages = [
        {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},
        {"role": "user", "content": f"Production error aaya hai: {error_message}"},
    ]

    response = call_llm(messages=messages, tools=all_tools)  # Pehli call - dono tools available
    message = response.choices[0].message

    # ---- Loop chalao jab tak LLM tool maangta rahe ----
    # (real agent me ye loop kai baar chal sakta hai - hum max 3 dafa allow karte hain safety ke liye)
    max_iterations = 3
    iteration = 0

    while message.tool_calls and iteration < max_iterations:  # Jab tak tool call ho aur limit na crosse
        iteration += 1                                          # Counter badhao (infinite loop se bachao)
        messages.append(message)                                 # Assistant ka message history me daalo

        for tool_call in message.tool_calls:                     # Har tool call ke liye
            tool_name = tool_call.function.name                    # Kaunsa tool
            tool_args = json.loads(tool_call.function.arguments)   # Arguments nikalo

            print(f"[TOOL CALL #{iteration}] {tool_name} with input: {tool_args}")

            # ---- Function map se actual Python function dhoond kar chalao ----
            func = tool_function_map.get(tool_name)                # Dictionary se function nikalo
            if func:
                result = func(**tool_args)                          # Function ko arguments ke sath call karo
            else:
                result = {"error": f"Unknown tool: {tool_name}"}     # Safety fallback

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": str(result),
                }
            )

        # ---- Agli LLM call - dekho ab aur tool chahiye ya final answer aa gaya ----
        response = call_llm(messages=messages, tools=all_tools)
        message = response.choices[0].message

    return message.content                                          # Final text diagnosis return karo


if __name__ == "__main__":
    # ---- Sample past incidents FAISS me pehle se load kar dete hain ----
    seed_incident_history(
        [
            "payment-service ne restart loop shuru kar diya OOM (out of memory) ki wajah se, fix: memory limit badhaya",
            "database connection timeout errors aa rahe the, fix: connection pool size increase kiya",
            "redis cache memory full ho gayi thi, fix: eviction policy allkeys-lru set ki",
        ]
    )

    sample_error = "payment-service container baar baar crash ho raha hai, high memory usage dikh raha hai"

    print("=" * 60)
    print("Running Day 2 Multi-Tool Diagnosis Test...")
    print("=" * 60)

    diagnosis = run_diagnosis(sample_error)
    print("\nFINAL DIAGNOSIS:\n")
    print(diagnosis)
