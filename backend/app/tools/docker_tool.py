# docker_tool.py
#
# Is file ka kaam: REAL Docker containers se baat karna.
# IMPORTANT: Abhi sirf READ-ONLY operations hain (status check, logs) -
# koi restart/stop/kill nahi - wo zyada risky hain, baad ke din me
# guardrails ke sath add karenge.

import docker                                    # Docker Python SDK

_client = None                                     # Module-level client - ek hi dafa banega


def _get_client():
    """
    Docker client ko LAZILY banata hai (jab pehli baar zaroorat ho) aur reuse karta hai.
    Docker Desktop (Windows/Mac) ya Docker daemon (Linux) chalta hona chahiye.
    """
    global _client                                 # global keyword - module-level variable update karne ke liye
    if _client is None:                              # Agar abhi tak nahi bana
        _client = docker.from_env()                    # Local Docker daemon se connect karo
    return _client


def check_container_status(container_name: str) -> dict:
    """
    Ek container ka LIVE status, image, aur basic info nikalta hai.
    """
    try:
        client = _get_client()                         # Docker client lo
        container = client.containers.get(container_name)  # Naam se container dhoondo

        return {
            "name": container.name,                       # Container ka naam
            "status": container.status,                     # "running" / "exited" / "paused" waghera
            "image": str(container.image.tags),               # Kaunsi image se bana hai
        }

    except docker.errors.NotFound:                       # Agar container exist hi nahi karta
        return {"error": f"Container '{container_name}' not found"}

    except Exception as e:                                 # Koi aur error (Docker na chal raha ho waghera)
        return {"error": f"Docker error: {str(e)}"}


def read_container_logs(container_name: str, tail: int = 50) -> dict:
    """
    Container ke RECENT logs padhta hai - diagnosis ke liye bohat useful.
    tail = kitni recent lines chahiye (default 50)
    """
    try:
        client = _get_client()
        container = client.containers.get(container_name)

        # container.logs() bytes return karta hai, isliye decode karna padta hai text me
        raw_logs = container.logs(tail=tail)                  # Last N lines fetch karo
        logs_text = raw_logs.decode("utf-8", errors="replace")   # Bytes -> readable text

        return {"container": container_name, "logs": logs_text}

    except docker.errors.NotFound:
        return {"error": f"Container '{container_name}' not found"}

    except Exception as e:
        return {"error": f"Docker error: {str(e)}"}


# ======================================================================
# Day 6 NAYA: WRITE action + GUARDRAIL
# ======================================================================

# GUARDRAIL: in naamon wale containers ko agent KABHI restart nahi kar sakta.
# Ye HARD-CODED rule hai - LLM kitna bhi convince kare, ye code check pehle chalega.
# (Databases/cache restart karne se data loss ya poora system down ho sakta hai)
PROTECTED_KEYWORDS = ("postgres", "redis", "mysql", "mongo", "database")


def restart_container(container_name: str, timeout: int = 10) -> dict:
    """
    Container ko RESTART karta hai - ye WRITE (risky) action hai.
    IMPORTANT: Is function ko call karne se PEHLE graph me human approval ho chuki hoti hai.
    """
    # ---- GUARDRAIL CHECK: protected container hai to seedha mana kar do ----
    lowered = container_name.lower()                           # Case-insensitive match ke liye
    for keyword in PROTECTED_KEYWORDS:
        if keyword in lowered:                                    # Naam me protected keyword mila
            return {
                "restarted": False,
                "error": f"GUARDRAIL: '{container_name}' protected container hai - restart allowed nahi",
            }

    try:
        client = _get_client()
        container = client.containers.get(container_name)          # Container dhoondo
        container.restart(timeout=timeout)                            # ACTUAL restart (timeout sec tak graceful stop ka wait)
        container.reload()                                             # Latest status docker se dobara fetch karo
        return {"restarted": True, "name": container.name, "status": container.status}

    except docker.errors.NotFound:
        return {"restarted": False, "error": f"Container '{container_name}' not found"}
    except Exception as e:
        return {"restarted": False, "error": f"Docker error: {str(e)}"}


# ---- Tool schemas (Groq/OpenAI-style) - future me LLM ko directly diye ja sakte hain ----
DOCKER_STATUS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "check_container_status",
        "description": "Check the live status (running/exited) and image of a Docker container.",
        "parameters": {
            "type": "object",
            "properties": {
                "container_name": {"type": "string", "description": "Exact name of the Docker container"}
            },
            "required": ["container_name"],
        },
    },
}

DOCKER_LOGS_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "read_container_logs",
        "description": "Read the most recent logs of a Docker container - useful for diagnosing crashes.",
        "parameters": {
            "type": "object",
            "properties": {
                "container_name": {"type": "string", "description": "Exact name of the Docker container"},
                "tail": {"type": "integer", "description": "Number of recent log lines to fetch (default 50)"},
            },
            "required": ["container_name"],
        },
    },
}
