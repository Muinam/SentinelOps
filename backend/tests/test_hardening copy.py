# test_hardening.py
#
# OFFLINE tests: LLM aur Docker ko FAKE kar ke aapke ASLI code (schemas, structured output,
# ReAct loop, critic, graph routing) ki logic check karta hai. Groq/Docker/internet ki zaroorat nahi.
# Ye temporary folder me chalta hai - aapka .env, Supabase aur logs/ ko nahi chhuta.
#
# Run (backend folder se):   python -m tests.test_hardening

import os                                                          # os - paths aur environment variables
import sys                                                         # sys - import path
import json                                                        # json - fake LLM ke jawab banane ke liye
import types                                                       # types - fake response objects ke liye
import hashlib                                                     # hashlib - fake embedding ke liye
import builtins                                                    # builtins - input() ko fake karne ke liye
import tempfile                                                    # tempfile - temporary folder
import contextlib                                                  # contextlib - stdout capture ke liye
import io                                                          # io - stdout buffer

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # backend folder ka absolute path
sys.path.insert(0, BACKEND)                                         # "app" import ke liye
TMP = tempfile.mkdtemp()                                            # Temporary folder (database, FAISS, logs yahin)
os.chdir(TMP)                                                       # Working directory badal do - logs/ yahin banega
os.environ["GROQ_API_KEY"] = "dummy"                                # Fake key (asli call hoti hi nahi)
for _name in ["POLICY_ALLOWED_CONTAINERS", "POLICY_DRY_RUN", "POLICY_AUTO_APPROVE", "NOTIFY_CHANNEL"]:   # Shell/.env ki policy se alag
    os.environ.pop(_name, None)                                      # Defaults par chalao (khali allowlist, human approval)
os.environ["CHECKPOINT_PATH"] = os.path.join(TMP, "cp.sqlite")      # Temporary checkpoint file
os.environ["POLICY_MAX_RESTARTS_PER_HOUR"] = "1000"                   # In purane tests me rate limit na aaye (uska alag test hai)
os.environ["GROQ_MODEL"] = "test-model"                             # Fake model naam
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{TMP}/test.db")   # Temporary SQLite (ya TEST_DATABASE_URL)
os.environ["FAISS_INDEX_PATH"] = f"{TMP}/idx.bin"                   # Temporary FAISS file

import numpy as np                                                  # numpy - fake embedding vectors
import app.rag.faiss_store as fs                                    # FAISS store module


def fake_embedding(text):
    """Model download ke bina 384-length deterministic vector banata hai."""
    vec = np.zeros(384, dtype="float32")                              # Khali vector
    for word in str(text).lower().split():                            # Har lafz ke liye
        vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % 384] += 1   # Hash se position chuno
    return (vec / (np.linalg.norm(vec) or 1)).astype("float32")        # Normalize


fs.get_embedding = fake_embedding                                     # Asli embedding ki jagah fake lagao

import app.llm.structured as structured                              # call_llm_json wala module
import app.agents.react as react_mod                                  # ReAct loop wala module
import app.agents.investigation_tools as inv_tools                    # ReAct ke tools
import app.agents.nodes.monitor_node as monitor_mod                   # Monitor node
import app.agents.nodes.executor_node as executor_mod                 # Executor node
import app.agents.nodes.verify_node as verify_mod                     # Verify node
from app.agents.schemas import Diagnosis, SolutionPlan, Critique      # Schemas
from app.agents.nodes.critic_node import grounded_ratio               # Grounding helper
from app.llm.structured import call_llm_json, StructuredOutputError   # JSON helper
from app.agents.react import run_react_loop                           # ReAct loop
import app.tools.rag_tool as rag_tool                                 # RAG memory (size check ke liye)
from app.db.database import Base, engine                             # Database setup
import app.db.models                                                  # Models import (tables register hon)
from sqlalchemy import create_engine, text as sql_text, inspect       # Migration test ke liye (sql_text - 'text' variable se na takraye)
from app.db.database import SessionLocal                              # DB session
from app.db import crud                                               # Lifecycle CRUD
import app.db.incidents as incidents_mod                              # Best-effort lifecycle helper
import app.tools.db_tool as db_tool_mod                               # Purana db tool (fallback test ke liye)
from app.db.migrate import ensure_schema                              # Migration

ensure_schema()                                                       # Temporary database tayyar karo (tables + naye columns)
verify_mod.VERIFY_INTERVAL = 0                                        # Test me intezar nahi

PASSED = []                                                           # Pass hue checks ki list


def ok(name):
    """Ek check pass hone ka record."""
    PASSED.append(name)                                               # List me daalo
    print(f"  PASS: {name}")                                          # Dikhao


# ---------------------------------------------------------------------------
# Fake LLM helpers
# ---------------------------------------------------------------------------
def make_response(content=None, tool_calls=None):
    """Groq response jaisa object banata hai."""
    message = types.SimpleNamespace(content=content, tool_calls=tool_calls)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


def make_tool_call(index, name, args):
    """Ek tool_call object banata hai."""
    return types.SimpleNamespace(id=f"call{index}", function=types.SimpleNamespace(name=name, arguments=json.dumps(args)))


class Queue:
    """Items ek ek kar ke deta hai; aakhri item baar baar repeat hota hai."""
    def __init__(self, items):
        self.items = list(items)                                       # Items ki copy
    def pop(self):
        return self.items.pop(0) if len(self.items) > 1 else self.items[0]   # Aakhri item repeat


class Fake:
    """Poore test ke liye ek jagah: LLM + Docker (MCP) ka fake."""
    def reset(self, diag, critic, solution, react="tool_then_final", status="running",
              logs="", restart_ok=True, verify=("running",)):
        self.diag = diag if callable(diag) else Queue(diag)             # Diagnosis jawab (queue ya function)
        self.critic = Queue(critic)                                      # Critic ke jawab
        self.solution = Queue(solution)                                  # Solution ke jawab
        self.react = react                                               # ReAct ka behavior
        self.status = status                                             # Container ka status
        self.logs = logs                                                 # Container ke logs
        self.restart_ok = restart_ok                                     # Restart kamyab ho?
        self.verify = Queue(verify)                                      # Verify ke status
        self.calls = []                                                  # Saari LLM calls: (kind, messages)
        self.inv_calls = []                                              # ReAct tools ki MCP calls
        self.restart_calls = 0                                           # Restart kitni dafa hua
        self.input_calls = 0                                             # Approval kitni dafa poochi gayi

    def llm(self, messages, tools=None, max_tokens=1024):
        """call_llm ki jagah: ReAct ya structured jawab deta hai."""
        if tools:                                                         # ReAct wali call
            self.calls.append(("react", [dict(m) for m in messages]))
            if self.react == "error":                                     # Tool-calling na chalne ka scenario
                raise RuntimeError("tools not supported by this model")
            if any(m.get("role") == "tool" for m in messages):            # Tool ka nateeja aa chuka
                return make_response(content="Investigation summary: see logs.")
            call = make_tool_call(1, "read_logs", {"tail": 20, "container_name": "SOME-OTHER-CONTAINER"})  # Ghalat container bhi maanga
            return make_response(tool_calls=[call])
        last = messages[-1]["content"]                                    # Aakhri message
        if '"title":"Diagnosis"' in last:
            item = self.diag(last) if callable(self.diag) else self.diag.pop()
            kind = "diag"
        elif '"title":"Critique"' in last:
            item, kind = self.critic.pop(), "critic"
        elif '"title":"SolutionPlan"' in last:
            item, kind = self.solution.pop(), "solution"
        else:                                                              # ReAct ka step-limit wala summary
            self.calls.append(("summary", messages))
            return make_response(content="summary text")
        self.calls.append((kind, [dict(m) for m in messages]))
        return make_response(content=item if isinstance(item, str) else json.dumps(item))

    def mcp_monitor(self, tool, args):
        """Monitor node ke MCP calls."""
        if tool == "docker_check_status":
            return {"name": args["container_name"], "status": self.status, "image": "['img']"}
        return {"container": args["container_name"], "logs": self.logs}

    def mcp_investigation(self, tool, args):
        """ReAct tools ke MCP calls (container record hota hai)."""
        self.inv_calls.append((tool, args))
        return self.mcp_monitor(tool, args)

    def mcp_executor(self, tool, args):
        """Executor ke MCP calls."""
        self.restart_calls += 1
        if self.restart_ok:
            return {"restarted": True, "name": args["container_name"], "status": "running"}
        return {"restarted": False, "error": "simulated docker failure"}

    def mcp_verify(self, tool, args):
        """Verify node ke MCP calls."""
        return {"name": args["container_name"], "status": self.verify.pop()}


fake = Fake()                                                             # Ek shared fake
structured.call_llm = fake.llm                                            # call_llm_json ab fake LLM use karega
react_mod.call_llm = fake.llm                                             # ReAct loop bhi
inv_tools.call_mcp_tool_json = fake.mcp_investigation                     # ReAct tools ka Docker
monitor_mod.call_mcp_tool_json = fake.mcp_monitor                         # Monitor ka Docker
executor_mod.call_mcp_tool_json = fake.mcp_executor                       # Executor ka Docker
verify_mod.call_mcp_tool_json = fake.mcp_verify                           # Verify ka Docker

from app.agents.graph import compiled_graph, RECURSION_LIMIT, MAX_RETRIES, MAX_REFLECTIONS   # Graph (fake patch ke BAAD import)

# ---------------------------------------------------------------------------
# Test data
# ---------------------------------------------------------------------------
ERR_LOGS = "2026-10-11 ERROR worker: out of memory: killed process 42\nfatal: connection pool exhausted"   # Asli error wale logs
INFO_LOGS = "/docker-entrypoint.sh: info: Configuration complete; ready for start up"                       # Sirf normal info
GOOD = {"fault_found": True, "root_cause": "The worker process was killed because it ran out of memory",
        "severity": "High", "evidence": ["out of memory: killed process 42"], "confidence": 0.8}            # Evidence asli logs me hai
HALLUCINATED = {"fault_found": True, "root_cause": "Nginx listens only on IPv6 so IPv4 requests fail",
                "severity": "High", "evidence": ["listens only on ipv6 so ipv4 fails"], "confidence": 0.9}   # Evidence logs me nahi
NO_FAULT = {"fault_found": False, "root_cause": "The container is running and the logs show only normal info messages",
            "severity": "Low", "evidence": ["status: running"], "confidence": 0.9}
CRITIC_OK = {"supported": True, "issues": [], "feedback": "Evidence directly supports the diagnosis"}
CRITIC_NO = {"supported": False, "issues": ["guess"], "feedback": "The cause is not visible in the evidence"}
SOL_RESTART = {"action": "restart_container", "explanation": "A restart clears the killed worker process"}
SOL_MANUAL = {"action": "manual_intervention", "explanation": "Increase the memory limit in the compose file"}


def base_state():
    """Graph ki shuruati state."""
    return {"error_message": "web-1 keeps crashing", "container_name": "web-1"}


def answers(*items):
    """input() ko scripted jawab dete hain; zyada maange to StopIteration (matlab approval galat jagah aayi)."""
    iterator = iter(items)
    def fake_input(prompt=""):
        fake.input_calls += 1                                              # Ginti
        return next(iterator)
    builtins.input = fake_input


def run(*inputs, limit=None, extra=None):
    """Graph chalata hai; (final_state, nodes_ka_order) return karta hai. extra - shuruati state me add hone wali cheezein."""
    answers(*inputs)
    buffer = io.StringIO()                                                  # Print ko pakadne ke liye
    with contextlib.redirect_stdout(buffer):
        start_state = {**base_state(), **(extra or {})}                      # Shuruati state + extra
        final = compiled_graph.invoke(start_state, {"recursion_limit": limit or RECURSION_LIMIT})
    nodes = [line.split()[1].replace("_node", "") for line in buffer.getvalue().splitlines() if line.startswith("[NODE]")]
    return final, nodes


def db_state(incident_id):
    """Database se incident row aur uske events ke status padhta hai."""
    db = SessionLocal()
    try:
        return crud.get_incident(db, incident_id), [e.status for e in crud.get_events(db, incident_id)]
    finally:
        db.close()


def incident_count():
    """Kul incident rows."""
    db = SessionLocal()
    try:
        return crud.count_incidents(db)
    finally:
        db.close()


# ===========================================================================
# UNIT TESTS
# ===========================================================================
print("\n[1] Schemas aur structured output")

assert Diagnosis(**{**GOOD, "severity": "  high "}).severity == "High"                      # Severity normalize
ok("severity 'high' -> 'High' normalize")
for bad in [{**GOOD, "severity": "High (likely)"}, {**GOOD, "confidence": 1.5}, {**GOOD, "evidence": []}]:
    try:
        Diagnosis(**bad)
        raise SystemExit("FAIL: invalid diagnosis accept ho gayi")
    except ValueError:
        pass
ok("lambi severity, confidence>1, khali evidence reject")

scripted = {"texts": []}                                                                    # call_llm_json ke liye alag script
structured.call_llm = lambda messages, tools=None, max_tokens=1024: make_response(content=scripted["texts"].pop(0))
scripted["texts"] = ["```json\n" + json.dumps(GOOD) + "\n```"]
assert call_llm_json([{"role": "user", "content": "x"}], Diagnosis).root_cause.startswith("The worker")
ok("code-fence wala JSON parse hota hai")
scripted["texts"] = ["not json at all", json.dumps({**GOOD, "severity": "Extreme"}), json.dumps(GOOD)]
assert call_llm_json([{"role": "user", "content": "x"}], Diagnosis, max_attempts=3).severity == "High"
ok("2 galat jawab ke baad repair loop se 3rd sahi mil jata hai")
scripted["texts"] = ["bad", "bad", "bad"]
try:
    call_llm_json([{"role": "user", "content": "x"}], Diagnosis, max_attempts=3)
    raise SystemExit("FAIL: error nahi aaya")
except StructuredOutputError:
    pass
ok("hamesha galat jawab par StructuredOutputError")
structured.call_llm = fake.llm                                                              # Dobara fake LLM

print("\n[2] ReAct loop")
fake.reset([GOOD], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS)
tools, tool_map = inv_tools.build_investigation_tools("web-1")
messages = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}]
with contextlib.redirect_stdout(io.StringIO()):
    text, trace = run_react_loop(messages, tools, tool_map, max_steps=3)
assert text.startswith("Investigation summary") and len(trace) == 1 and trace[0]["tool"] == "read_logs"
ok("LLM ne tool chuna, observation mila, phir final jawab")
assert fake.inv_calls[0][1]["container_name"] == "web-1"
ok("LLM ne 'SOME-OTHER-CONTAINER' maanga lekin tool ne incident wala container hi use kiya (guardrail)")
assert all(t["function"]["name"] != "docker_restart" for t in tools)
ok("investigation tools me restart jaisa write tool nahi hai")
with contextlib.redirect_stdout(io.StringIO()):
    text, trace = run_react_loop([{"role": "user", "content": "u"}], tools, {"read_logs": lambda **a: 1 / 0}, max_steps=2)
assert "tool failed" in trace[0]["observation"]
ok("tool crash hone par loop nahi tootta, error observation banta hai")
with contextlib.redirect_stdout(io.StringIO()):
    text, trace = run_react_loop([{"role": "user", "content": "u"}], tools, {}, max_steps=2)
assert "unknown tool" in trace[0]["observation"]
ok("unknown tool par error observation")
original_llm = react_mod.call_llm
react_mod.call_llm = lambda messages, tools=None, max_tokens=1024: (
    make_response(tool_calls=[make_tool_call(1, "read_logs", {})]) if tools else make_response(content="forced summary"))
with contextlib.redirect_stdout(io.StringIO()):
    text, trace = run_react_loop([{"role": "user", "content": "u"}], tools, tool_map, max_steps=3)
assert text == "forced summary" and len(trace) == 3
react_mod.call_llm = original_llm
ok("LLM hamesha tool maange to max_steps par ruk kar summary leta hai (infinite loop nahi)")

print("\n[3] Grounding check (hallucination detector)")
pool = json.dumps({"status": "running", "recent_logs": ERR_LOGS})
assert grounded_ratio(["out of memory: killed process 42"], pool)[0] == 1.0
ok("asli log ka quote grounded")
assert grounded_ratio(["status: running"], pool)[0] == 1.0
ok("JSON ke andar ka status bhi match hota hai")
ratio, missing = grounded_ratio(["listens only on ipv6 so ipv4 fails"], pool)
assert ratio == 0.0 and missing
ok("banaya hua quote pakda gaya")
assert grounded_ratio([], pool)[0] == 0.0
ok("khali evidence = 0")

# ===========================================================================
# GRAPH TESTS (langgraph ka wahi version jo aap use kar rahe hain)
# ===========================================================================
print("\n[4] Graph ke raaste")

# ---- G1: poora kamyab raasta ----
fake.reset([GOOD], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS)
before = rag_tool.memory_size()
final, nodes = run("y")
assert nodes == ["intake", "monitor", "diagnosis", "critic", "solution", "policy", "approval", "executor", "verify", "reporter"], nodes
assert final["verified"] and final["incident_id"] is not None and rag_tool.memory_size() == before + 1
assert final["severity"] == "High" and final["diagnosis_evidence"] and len(final["react_trace"]) == 1
row, events = db_state(final["incident_id"])
assert row.status == "resolved" and row.resolved_at is not None and row.container_name == "web-1"
assert row.severity == "High" and row.recommended_action == "restart_container" and row.confidence == 0.8
assert events == ["investigating", "awaiting_approval", "executing", "verifying", "resolved"], events
ok("G1 poora raasta: monitor>diagnosis>critic>solution>policy>approval>executor>verify>reporter, DB+FAISS me save")

# ---- G2: reflection - pehli diagnosis hallucinated, critic wapas bheje, doosri theek ----
fake.reset([HALLUCINATED, GOOD], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS)
final, nodes = run("y")
assert nodes[:6] == ["intake", "monitor", "diagnosis", "critic", "diagnosis", "critic"], nodes
second_prompt = [m for kind, m in fake.calls if kind == "diag"][1][-1]["content"]
assert "REVIEWER REJECTED" in second_prompt and "NOT found" in second_prompt
assert final["verified"]
ok("G2 reflection: hallucinated diagnosis pakdi gayi, hidayat ke sath dobara diagnose, phir kamyab")

# ---- G3: hamesha hallucinated - limit ke baad insaan ----
fake.reset([HALLUCINATED], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS)
final, nodes = run()
assert nodes == ["intake", "monitor", "diagnosis", "critic", "diagnosis", "critic", "rejected"], nodes
assert fake.restart_calls == 0
row, events = db_state(final["incident_id"])
assert row.status == "needs_review" and row.review_reason.startswith("Diagnosis not supported")
assert events == ["investigating", "needs_review"], events          # Reflection loop me status wahi raha, shor nahi
assert final["review_reason"].startswith("Diagnosis not supported by evidence")
assert not [1 for kind, _ in fake.calls if kind == "critic"]
ok("G3 hamesha hallucinated: 2 koshish ke baad rejected, restart nahi hua, critic LLM tak baat gayi hi nahi (sasta check ne rok diya)")

# ---- G4: koi fault nahi (nginx wala asal scenario) ----
fake.reset([NO_FAULT], [CRITIC_OK], [SOL_RESTART], logs=INFO_LOGS)
final, nodes = run()
assert nodes == ["intake", "monitor", "diagnosis", "critic", "rejected"], nodes
assert final["review_reason"].startswith("No fault found") and fake.restart_calls == 0
row, events = db_state(final["incident_id"])
assert row.status == "needs_review" and row.review_reason.startswith("No fault found")
ok("G4 container theek hai, user ka dawa jhoota: 'No fault found', koi action nahi")

# ---- G5: manual intervention ----
fake.reset([GOOD], [CRITIC_OK], [SOL_MANUAL], logs=ERR_LOGS)
final, nodes = run()
assert nodes == ["intake", "monitor", "diagnosis", "critic", "solution", "rejected"], nodes
assert fake.input_calls == 0 and fake.restart_calls == 0
assert final["review_reason"].startswith("Manual intervention needed")
ok("G5 restart ilaaj nahi: approval poocha hi nahi, seedha insaan")

# ---- G6: insaan ne na kaha ----
fake.reset([GOOD], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS)
final, nodes = run("n")
assert nodes[-2:] == ["approval", "rejected"] and fake.restart_calls == 0
assert final["review_reason"] == "A human rejected the proposed action."
row, events = db_state(final["incident_id"])
assert row.status == "needs_review" and row.review_reason == "A human rejected the proposed action."
assert events == ["investigating", "awaiting_approval", "needs_review"], events
ok("G6 insaan ne 'no' kaha: executor chala hi nahi")

# ---- G7: restart kamyab lekin verify fail (container phir gir gaya) ----
fake.reset([GOOD], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS, verify=("restarting",))
final, nodes = run("y", "y", "y")
assert nodes.count("executor") == 3 and nodes.count("verify") == 3 and nodes[-1] == "rejected"
assert final["retry_count"] == MAX_RETRIES + 1 and not final["verified"]
row, events = db_state(final["incident_id"])
assert row.status == "needs_review" and row.retry_count == MAX_RETRIES + 1 and events.count("executing") == 3, events
assert "did not become healthy" in final["review_reason"]
ok("G7 restart ke baad container healthy nahi mila: 3 koshish ke baad rejected (pehle ise 'success' maan lete)")

# ---- G8: worst case loops aur recursion limit ----
def halluc_first(prompt):
    """Har naye cycle me pehli diagnosis hallucinated; critic ki hidayat milne par theek."""
    return GOOD if "REVIEWER REJECTED" in prompt else HALLUCINATED
fake.reset(halluc_first, [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS, verify=("restarting",))
final, nodes = run("y", "y", "y")
assert len(nodes) > 25, len(nodes)
ok(f"G8 worst case me graph {len(nodes)} steps leta hai (LangGraph ki default limit 25 se zyada)")
fake.reset(halluc_first, [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS, verify=("restarting",))
try:
    run("y", "y", "y", limit=25)
    raise SystemExit("FAIL: default limit par error aana chahiye tha")
except Exception as error:
    assert type(error).__name__ == "GraphRecursionError", type(error).__name__
ok("G8b default limit (25) par GraphRecursionError aata - isliye RECURSION_LIMIT=60 zaroori hai")

# ---- G9: LLM valid JSON hi na de ----
fake.reset(["this is not json"], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS)
final, nodes = run()
assert nodes[-1] == "rejected" and fake.restart_calls == 0
assert final["review_reason"].startswith("Diagnosis not supported by evidence")
ok("G9 LLM kharab JSON de to graph crash nahi hota, insaan ke paas jata hai")

# ---- G10: model tool-calling support na kare ----
fake.reset([GOOD], [CRITIC_OK], [SOL_RESTART], react="error", logs=ERR_LOGS)
final, nodes = run("y")
assert final["verified"] and final["react_trace"] == []
ok("G10 ReAct fail (tool-calling nahi) to baseline data par diagnosis chalti hai, crash nahi")

print("\n[5] Incident lifecycle (database)")

# ---- L1: ek run = ek hi row ----
fake.reset([GOOD], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS)
rows_before = incident_count()
final, nodes = run("y")
assert incident_count() == rows_before + 1
ok("L1 ek run = ek hi incident row (reporter ne duplicate nahi banaya)")

# ---- L2: pehle se bana hua incident (aage watcher/API aise denge) ----
pre_id = incidents_mod.open_incident("pre-made incident", "web-1")
rows_before = incident_count()
fake.reset([GOOD], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS)
final, nodes = run("y", extra={"incident_id": pre_id})
assert final["incident_id"] == pre_id and incident_count() == rows_before
assert db_state(pre_id)[0].status == "resolved"
ok("L2 state me pehle se incident_id ho to wahi row use hoti hai, naya nahi banta")

# ---- L3: database band ho to bhi graph crash nahi karta ----
def broken_session():
    raise RuntimeError("database down")
saved = (incidents_mod.SessionLocal, db_tool_mod.SessionLocal)
incidents_mod.SessionLocal = broken_session
db_tool_mod.SessionLocal = broken_session
try:
    fake.reset([GOOD], [CRITIC_OK], [SOL_RESTART], logs=ERR_LOGS)
    final, nodes = run("y")
finally:
    incidents_mod.SessionLocal, db_tool_mod.SessionLocal = saved
assert final["verified"] and final["incident_id"] is None and nodes[-1] == "reporter" and fake.restart_calls == 1
ok("L3 database band hone par bhi container theek hota hai (graph crash nahi), sirf record nahi banta")

# ---- L4: purani Day-2 table ka migration, purani rows safe ----
old_engine = create_engine(f"sqlite:///{TMP}/old_day2.db")
with old_engine.begin() as conn:
    conn.execute(sql_text("CREATE TABLE incidents (id INTEGER PRIMARY KEY, error_message TEXT NOT NULL, diagnosis TEXT, severity VARCHAR(20), status VARCHAR(20), created_at DATETIME)"))
    conn.execute(sql_text("INSERT INTO incidents (error_message, diagnosis, severity, status) VALUES ('old error', 'old diagnosis', 'High', 'open')"))
added = ensure_schema(old_engine)
for expected in ["incidents.container_name", "incidents.retry_count", "incidents.review_reason", "incidents.resolved_at"]:
    assert expected in added, (expected, added)
with old_engine.connect() as conn:
    old_row = conn.execute(sql_text("SELECT error_message, diagnosis, status, retry_count FROM incidents")).one()
assert tuple(old_row) == ("old error", "old diagnosis", "open", 0), tuple(old_row)
assert "incident_events" in inspect(old_engine).get_table_names()
assert ensure_schema(old_engine) == []
ok("L4 purani table me naye columns jude, purani row safe (retry_count=0), events table bani, dobara chalane par kuch nahi badla")

# ---- L5: update ki whitelist ----
db = SessionLocal()
try:
    crud.update_incident(db, pre_id, id=999)
    raise SystemExit("FAIL: id update ho gayi")
except ValueError:
    pass
finally:
    db.close()
ok("L5 incident ke sirf allowed columns update ho sakte hain (id nahi)")

print(f"\nALL {len(PASSED)} CHECKS PASSED")
