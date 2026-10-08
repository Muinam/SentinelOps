from app.llm import client
import docker

_client = None

def _get_client():
    """
    Docker client ko LAZILY banata hai (jab pehli baar zaroorat ho) aur reuse karta hai.
    Docker Desktop (Windows/Mac) ya Docker daemon (Linux) chalta hona chahiye.
    """
    global _client
    if _client is None:
        _client = docker.from_env()
    return _client

def check_container_status(container_name:str) -> dict:
    """
    Ek container ka LIVE status, image, aur basic info nikalta hai.
    """

    try:
        client = _get_client()
        container = client.containers.get(container_name)

        return{
            'name':container.name,
            'status':container.status,
            'image': str(container.image.tags)
        }


    except docker.errors.NotFound:
        return {"error": f"Container {container_name} not found"}

    except Exception as e:
        return {"error": f"Docker Error: {str(e)}"}


def read_container_logs(container_name:str, tail: int=50) -> dict:
    """
    Container ke RECENT logs padhta hai - diagnosis ke liye bohat useful.
    tail = kitni recent lines chahiye (default 50)
    """

    try: 
        client = _get_client()
        container = client.containers.get(container_name)
        
        # container.logs() bytes return karta hai, isliye decode karna padta hai text me
        raw_logs = container.logs(tail=tail)
        logs_text = raw_logs.decode('utf-8', errors='replace')
        
        return{'container': container_name, 'logs': logs_text}

    except docker.errors.NotFound:
        return {'error': f'Container {container_name} not found'}

    except Exception as e:
        return {'error': f'Docker Error: {str(e)}'}


PROTECTED_KEYWORDS = ("postgres", "redis", "mysql", "mongo", "database")


def restart_container(container_name:str, timeout: int=10)->dict:
    """
    Container ko RESTART karta hai - ye WRITE (risky) action hai.
    IMPORTANT: Is function ko call karne se PEHLE graph me human approval ho chuki hoti hai.
    """
    lowered = container_name.lower()

    for keyword in PROTECTED_KEYWORDS:
        if keyword in lowered:
            return {'error': f'Restarting protected container {container_name} is not allowed'}
    
    try:
        client = _get_client()
        container = client.containers.get(container_name)
        container.restart(timeout=timeout)
        container.reload()

        return {'restarted': True, 'name': container_name, 'status':container.status, }
    
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
