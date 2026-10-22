# fakes.py
#
# Tests ke liye FAKE LLM + Docker (MCP). test_api.py yahin se leta hai (taake wahi cheez do jagah na likhni pade).
# install(fake) ko env variables set karne aur os.chdir ke BAAD call karein.

import json                                                         # json - fake LLM ke jawab
import types                                                        # types - fake objects
import hashlib                                                      # hashlib - fake embedding
import numpy as np                                                  # numpy - fake embedding vector


def fake_embedding(text):
    """Model download ke bina 384-length vector."""
    vec = np.zeros(384, dtype="float32")
    for word in str(text).lower().split():
        vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % 384] += 1
    return (vec / (np.linalg.norm(vec) or 1)).astype("float32")


def response(content=None, tool_calls=None):
    """Groq response jaisa object."""
    message = types.SimpleNamespace(content=content, tool_calls=tool_calls)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


class Fake:
    """Fake LLM aur Docker. Diagnosis hamesha 'out of memory' wali, evidence asli logs me hota hai."""

    def __init__(self):
        self.reset()

    def reset(self, severity="High", confidence=0.8):
        self.severity = severity
        self.confidence = confidence
        self.restart_calls = 0
        self.logs = "2026-10-11 ERROR worker: out of memory: killed process 42"

    def llm(self, messages, tools=None, max_tokens=1024):
        if tools:                                                    # ReAct: ek tool call phir jawab
            if any(m.get("role") == "tool" for m in messages):
                return response(content="summary")
            call = types.SimpleNamespace(id="c1", function=types.SimpleNamespace(name="read_logs", arguments="{}"))
            return response(tool_calls=[call])
        last = messages[-1]["content"]
        if '"title":"Diagnosis"' in last:
            item = {"fault_found": True, "root_cause": "The worker process was killed because it ran out of memory",
                    "severity": self.severity, "evidence": ["out of memory: killed process 42"], "confidence": self.confidence}
        elif '"title":"Critique"' in last:
            item = {"supported": True, "issues": [], "feedback": "Evidence supports the diagnosis"}
        elif '"title":"SolutionPlan"' in last:
            item = {"action": "restart_container", "explanation": "A restart clears the killed worker process"}
        else:
            return response(content="summary")
        return response(content=json.dumps(item))

    def mcp_read(self, tool, args):
        if tool == "docker_check_status":
            return {"name": args["container_name"], "status": "exited", "image": "['img']"}
        return {"container": args["container_name"], "logs": self.logs}

    def mcp_restart(self, tool, args):
        self.restart_calls += 1
        return {"restarted": True, "name": args["container_name"], "status": "running"}

    def mcp_verify(self, tool, args):
        return {"name": args["container_name"], "status": "running"}


def install(fake):
    """Asli modules me fake LLM/Docker/embedding laga deta hai."""
    import app.rag.faiss_store as fs
    import app.llm.structured as structured
    import app.agents.react as react_mod
    import app.agents.investigation_tools as inv_tools
    import app.agents.nodes.monitor_node as monitor_mod
    import app.agents.nodes.executor_node as executor_mod
    import app.agents.nodes.verify_node as verify_mod
    fs.get_embedding = fake_embedding
    structured.call_llm = fake.llm
    react_mod.call_llm = fake.llm
    inv_tools.call_mcp_tool_json = fake.mcp_read
    monitor_mod.call_mcp_tool_json = fake.mcp_read
    executor_mod.call_mcp_tool_json = fake.mcp_restart
    verify_mod.call_mcp_tool_json = fake.mcp_verify
    verify_mod.VERIFY_INTERVAL = 0
