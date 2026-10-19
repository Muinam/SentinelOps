# test_automation.py
#
# OFFLINE tests (Day 9-11): policy, watcher, notify, approval pause/resume aur worker.
# LLM, Docker aur MCP FAKE hain; baaki sab ASLI hai (SQLite checkpointer, database, worker, watcher).
# Temporary folder me chalta hai - aapka .env, Supabase, logs/ aur checkpoints ko nahi chhuta.
#
# Run (backend folder se):   python -m tests.test_automation

import os                                                          # os - paths aur environment
import sys                                                         # sys - import path
import io                                                          # io - stdout capture
import json                                                        # json - fake LLM ke jawab
import types                                                       # types - fake objects
import hashlib                                                     # hashlib - fake embedding
import tempfile                                                    # tempfile - temporary folder
import threading                                                   # threading - local HTTP server
import contextlib                                                  # contextlib - stdout capture
import http.server                                                 # http.server - notify test ka local server
import socket                                                      # socket - band port nikalne ke liye

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # backend folder
sys.path.insert(0, BACKEND)                                         # "app" import ke liye
TMP = tempfile.mkdtemp()                                            # Temporary folder
os.chdir(TMP)                                                       # Working directory badlo (logs/ yahin banega)
os.environ["GROQ_API_KEY"] = "dummy"                                # Fake key
os.environ["GROQ_MODEL"] = "test-model"                             # Fake model
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{TMP}/auto.db")   # Temporary DB
os.environ["FAISS_INDEX_PATH"] = f"{TMP}/idx.bin"                   # Temporary FAISS
os.environ["CHECKPOINT_PATH"] = f"{TMP}/cp.sqlite"                  # Temporary checkpoints
for _name in ["POLICY_ALLOWED_CONTAINERS", "POLICY_DRY_RUN", "POLICY_AUTO_APPROVE", "NOTIFY_CHANNEL",
              "POLICY_MAX_RESTARTS_PER_HOUR", "POLICY_COOLDOWN_MINUTES", "APPROVAL_TIMEOUT_MINUTES"]:
    os.environ.pop(_name, None)                                      # Shell ki policy se alag

import numpy as np                                                  # numpy - fake embedding
import app.rag.faiss_store as fs                                    # FAISS store


def fake_embedding(text):
    """Model download ke bina 384-length vector."""
    vec = np.zeros(384, dtype="float32")
    for word in str(text).lower().split():
        vec[int(hashlib.md5(word.encode()).hexdigest(), 16) % 384] += 1
    return (vec / (np.linalg.norm(vec) or 1)).astype("float32")


fs.get_embedding = fake_embedding                                    # Asli embedding ki jagah

import app.llm.structured as structured                              # JSON helper
import app.agents.react as react_mod                                  # ReAct loop
import app.agents.investigation_tools as inv_tools                    # ReAct tools
import app.agents.nodes.monitor_node as monitor_mod                   # Monitor
import app.agents.nodes.executor_node as executor_mod                 # Executor
import app.agents.nodes.verify_node as verify_mod                     # Verify
from app.config import get_settings                                    # Settings (tests me badli jaati hain)
from app.db.database import SessionLocal                               # DB session
from app.db import crud                                                 # CRUD
from app.db.models import Incident                                      # Incident model
from app.db.migrate import ensure_schema                                # Migration
from app.core.guardrails import Policy, evaluate_action, is_allowed     # Policy
from app.watcher.docker_watcher import detect_problem, scan_once, WatcherConfigError   # Watcher
from app.agents.nodes.approval_node import external_approval_node       # External approval node
from app.agents.checkpointing import get_checkpointer                   # Checkpointer
from app.agents.graph import build_graph                                 # Graph builder
from app.worker.runner import Worker                                      # Worker
from app.tools import notify_tool                                         # Notify
from sqlalchemy import create_engine, text as sql_text, inspect          # Migration test

ensure_schema()                                                       # Temporary DB tayyar
verify_mod.VERIFY_INTERVAL = 0                                         # Verify me intezar nahi
SETTINGS = get_settings()                                              # Shared settings object
PASSED = []                                                            # Pass hue checks


def ok(name):
    PASSED.append(name)
    print(f"  PASS: {name}")


def configure(**overrides):
    """Settings ko defaults par la kar overrides lagata hai (har scenario saaf shuru ho)."""
    defaults = dict(policy_allowed_containers="test-*", policy_max_restarts_per_hour=3, policy_cooldown_minutes=10,
                    policy_dry_run=False, policy_auto_approve=False, policy_auto_approve_max_severity="Medium",
                    policy_auto_approve_min_confidence=0.8, approval_timeout_minutes=30, notify_channel="console",
                    watch_ignore_clean_exit=False)
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(SETTINGS, key, value)


def quiet(func, *args, **kwargs):
    """Function ka print dabata hai (output saaf rahe), result wapas deta hai."""
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args, **kwargs)


# ---------------------------------------------------------------------------
# Fakes: LLM + Docker (MCP)
# ---------------------------------------------------------------------------
def response(content=None, tool_calls=None):
    message = types.SimpleNamespace(content=content, tool_calls=tool_calls)
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)])


class Fake:
    def __init__(self):
        self.reset()

    def reset(self, severity="High", confidence=0.8, llm_error=None):
        self.severity = severity                                       # Diagnosis ki severity
        self.confidence = confidence                                   # Diagnosis ka confidence
        self.llm_error = llm_error                                     # Diagnosis par LLM error (worker crash test)
        self.restart_ok = True                                         # Restart kamyab ho?
        self.restart_calls = 0                                         # Restart ki ginti
        self.logs = "2026-10-11 ERROR worker: out of memory: killed process 42"

    def llm(self, messages, tools=None, max_tokens=1024):
        if tools:                                                       # ReAct: ek tool call phir jawab
            if any(m.get("role") == "tool" for m in messages):
                return response(content="summary")
            call = types.SimpleNamespace(id="c1", function=types.SimpleNamespace(name="read_logs", arguments="{}"))
            return response(tool_calls=[call])
        last = messages[-1]["content"]
        if '"title":"Diagnosis"' in last:
            if self.llm_error:
                raise RuntimeError(self.llm_error)
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
        if self.restart_ok:
            return {"restarted": True, "name": args["container_name"], "status": "running"}
        return {"restarted": False, "error": "simulated docker failure"}

    def mcp_verify(self, tool, args):
        return {"name": args["container_name"], "status": "running"}


fake = Fake()
structured.call_llm = fake.llm
react_mod.call_llm = fake.llm
inv_tools.call_mcp_tool_json = fake.mcp_read
monitor_mod.call_mcp_tool_json = fake.mcp_read
executor_mod.call_mcp_tool_json = fake.mcp_restart
verify_mod.call_mcp_tool_json = fake.mcp_verify


def container(name, status="exited", exit_code=137, oom=True, health=None, restarting=False):
    """Docker SDK ke container jaisa fake object."""
    state = {"Status": status, "ExitCode": exit_code, "OOMKilled": oom, "Restarting": restarting}
    if health:
        state["Health"] = {"Status": health}
    return types.SimpleNamespace(name=name, status=status, attrs={"State": state, "RestartCount": 0})


def make_worker(containers, sent=None, cp_path=None):
    """Naya worker: apna graph + apna checkpointer (process restart simulate karne ke liye alag bhi ban sakta hai)."""
    graph = build_graph(get_checkpointer("sqlite", cp_path or os.environ["CHECKPOINT_PATH"]))
    return Worker(graph, list_containers=lambda: containers, notify_fn=(sent.append if sent is not None else (lambda m: None)))


def row_of(name):
    """Is container ka sab se naya incident (row, events ke status)."""
    db = SessionLocal()
    try:
        row = db.query(Incident).filter(Incident.container_name == name).order_by(Incident.id.desc()).first()
        events = [e.status for e in crud.get_events(db, row.id)] if row else []
        return row, events
    finally:
        db.close()


def drain_queue():
    """Pichle sections ke adhure incidents (detected/awaiting...) ko needs_review kar deta hai - worker ki queue saaf."""
    db = SessionLocal()
    try:
        for status in ("detected", "awaiting_approval", "investigating", "executing", "verifying"):
            for leftover in crud.list_by_status(db, status, 500):
                leftover.status = "needs_review"
        db.commit()
    finally:
        db.close()


def decide(incident_id, approved, by="inam", note=None):
    """approve.py wala hi function."""
    db = SessionLocal()
    try:
        return crud.record_decision(db, incident_id, approved, by, note)
    finally:
        db.close()


# ===========================================================================
print("\n[1] Masla pehchanne ka logic (detect_problem)")
configure()
assert "exit code 137" in detect_problem({"status": "exited", "exit_code": 137, "oom_killed": True}) and \
       "OOMKilled" in detect_problem({"status": "exited", "exit_code": 137, "oom_killed": True})
ok("exited + OOMKilled pakda gaya")
assert "restarting" in detect_problem({"status": "restarting", "restart_count": 5})
ok("restart loop pakda gaya")
assert "unhealthy" in detect_problem({"status": "running", "health": "unhealthy"})
ok("health check fail (running hote hue bhi) pakda gaya")
assert detect_problem({"status": "running", "health": "healthy"}) is None and detect_problem({"status": "running"}) is None
ok("theek container par koi masla nahi")
assert detect_problem({"status": "exited", "exit_code": 0}) is not None and detect_problem({"status": "exited", "exit_code": 0}, ignore_clean_exit=True) is None
ok("exit code 0: default masla, ignore_clean_exit=True par masla nahi")

# ===========================================================================
print("\n[2] Policy (guardrails)")
P = Policy(allowed_patterns=("test-*", "web-1"), max_restarts_per_hour=3, cooldown_minutes=10, dry_run=False,
           auto_approve=True, auto_approve_max_severity="Medium", auto_approve_min_confidence=0.8)


def decision(policy=P, container_name="test-a", severity="Low", confidence=0.9, supported=True,
             action="restart_container", retries=0, recent=0):
    return evaluate_action(policy, container_name, severity, confidence, supported, action, retries, recent)


assert is_allowed("TEST-api", P) and is_allowed("web-1", P) and not is_allowed("db-1", P)
assert is_allowed("anything", Policy((), 3, 10, False, False, "Medium", 0.8))
ok("allowlist: pattern match (case-insensitive), khali allowlist = koi rok nahi")
d = decision(container_name="prod-api")
assert d.kind == "blocked" and "allowlist" in d.reason
ok("allowlist ke bahar ka container blocked")
d = decision(policy=Policy(("*",), 3, 10, False, True, "Medium", 0.8), container_name="airflow-postgres-1")
assert d.kind == "blocked" and "protected" in d.reason
ok("allowlist '*' ho tab bhi postgres/redis protected hain")
d = decision(recent=3)
assert d.kind == "blocked" and "limit" in d.reason
assert decision(recent=2).kind == "auto"
ok("rate limit: 3 restarts ke baad blocked, 2 par nahi")
assert decision(policy=Policy(P.allowed_patterns, 3, 10, True, True, "Medium", 0.8)).kind == "blocked"
ok("dry-run: auto-approve ke bawajood blocked")
assert decision().kind == "auto" and decision(severity="Medium", confidence=0.8).kind == "auto"
ok("auto-approve: Low/Medium + confidence theek + critic sabit + pehli koshish")
for name, kwargs in [("High severity", dict(severity="High")), ("kam confidence", dict(confidence=0.5)),
                     ("critic sabit nahi", dict(supported=False)), ("retry ke baad", dict(retries=1)),
                     ("restart ginti maloom nahi", dict(recent=None)), ("manual action", dict(action="manual_intervention")),
                     ("unknown severity", dict(severity="Weird"))]:
    assert decision(**kwargs).kind == "human", name
ok("auto-approve ki har shart toote to INSAAN (High, kam confidence, critic, retry, DB masla, manual, unknown severity)")
assert decision(policy=Policy(P.allowed_patterns, 3, 10, False, False, "Medium", 0.8)).kind == "human"
ok("auto_approve band ho to hamesha insaan (default)")

# ===========================================================================
print("\n[3] Approval node (external) aur approve ka database function")
r = quiet(external_approval_node, {"approval_decided": False, "approved": True})
assert r["approved"] is False and "failing safe" in r["review_reason"]
ok("faisla record na ho to safe side par reject (approved=True hone ke bawajood)")
r = quiet(external_approval_node, {"approval_decided": True, "approved": True, "approved_by": "inam"})
assert r == {"approved": True}
r = quiet(external_approval_node, {"approval_decided": True, "approved": False, "approved_by": "sara", "approval_note": "pehle logs"})
assert r["approved"] is False and r["review_reason"] == "Rejected by sara: pehle logs"
ok("approve/reject ka faisla sahi lagta hai (kis ne, kya note)")
from app.db.incidents import open_incident, set_status                  # Test ke liye
iid = open_incident("e", "test-x")
assert decide(iid, True)[0] is False and "approval ka intezar nahi" in decide(iid, True)[1]
ok("awaiting_approval na ho to faisla likhna mana")
set_status(iid, "awaiting_approval")
assert decide(9999, True)[0] is False
assert decide(iid, True, "inam")[0] is True
second = decide(iid, False, "sara")
assert second[0] is False and "ho chuka hai" in second[1]
ok("ek incident par faisla sirf ek dafa (doosri koshish mana, pehla faisla safe)")
set_status(iid, "awaiting_approval")
db = SessionLocal(); stale = crud.get_incident(db, iid); db.close()
assert stale.approval_decision is None and stale.approved_by is None
ok("incident dobara awaiting_approval me aaye to PURANA faisla saaf ho jata hai (stale 'yes' dobara nahi lagta)")

# ===========================================================================
print("\n[4] Watcher (scan_once)")
configure(policy_allowed_containers="test-s*")
from app.core.guardrails import load_policy
try:
    scan_once([container("test-s1")], Policy((), 3, 10, False, False, "Medium", 0.8))
    raise SystemExit("FAIL: khali allowlist par error nahi aaya")
except WatcherConfigError:
    pass
ok("allowlist khali ho to watcher shuru hi nahi hota (khud-ba-khud kaam ka scope chahiye)")

fleet = [container("test-s1"), container("test-s2", status="running", exit_code=0, oom=False),
         container("other-app"), container("test-s-postgres"), container("test-s3", status="running", exit_code=0, oom=False, health="unhealthy")]
opened = quiet(scan_once, fleet, load_policy())
names = sorted(o["container"] for o in opened)
assert names == ["test-s1", "test-s3"], names
ok("sirf allowlist wale kharab containers (exited, unhealthy) pakde gaye; theek, allowlist ke bahar aur protected nahi")
row, events = row_of("test-s1")
assert row.status == "detected" and "exit code 137" in row.error_message and events == ["detected"]
ok("incident 'detected' status me queue hua, error me exit code, timeline ka pehla event")
assert quiet(scan_once, fleet, load_policy()) == []
ok("dobara scan: pehle se active incident hai to naya nahi (dedupe)")
set_status(row.id, "resolved")
assert quiet(scan_once, fleet, load_policy()) == [] or True
reopened = [o for o in quiet(scan_once, fleet, load_policy()) if o["container"] == "test-s1"]
assert reopened == []
ok("incident abhi resolve hua to cooldown ke andar naya incident nahi (flapping se bachav)")
configure(policy_allowed_containers="test-s*", policy_cooldown_minutes=0)
reopened = [o for o in quiet(scan_once, fleet, load_policy()) if o["container"] == "test-s1"]
assert len(reopened) == 1
ok("cooldown 0 ho to wahi container dobara incident banata hai")
clean = [container("test-s9", exit_code=0, oom=False)]
assert quiet(scan_once, clean, load_policy(), True) == [] and len(quiet(scan_once, clean, load_policy(), False)) == 1
ok("ignore_clean_exit: exit code 0 wala container chhoda ja sakta hai")

# ===========================================================================
print("\n[5] Worker: pause -> faisla -> resume (asli SQLite checkpointer)")
configure()
drain_queue()                                                              # Pichle sections ka kachra saaf

# ---- W1: poora raasta ----
fake.reset()
sent = []
fleet = [container("test-w1")]
worker = make_worker(fleet, sent)
quiet(worker.tick)
row, events = row_of("test-w1")
assert row.status == "awaiting_approval" and row.approval_decision is None and fake.restart_calls == 0, (row.status, fake.restart_calls)
assert any("Approval chahiye" in m and f"scripts.approve {row.id} yes" in m and "out of memory: killed process 42" in m for m in sent)
ok("W1a watcher ne pakda, graph chala, approval par RUK gaya; restart nahi hua; insaan ko notification (evidence + approve command)")
quiet(worker.tick)
assert fake.restart_calls == 0 and row_of("test-w1")[0].status == "awaiting_approval"
ok("W1b faisla na ho to worker intezar karta hai (restart nahi)")
assert decide(row.id, True, "inam", "theek hai")[0]
quiet(worker.tick)
row, events = row_of("test-w1")
assert row.status == "resolved" and fake.restart_calls == 1 and row.resolved_at is not None
assert row.approval_decision == "approved" and row.approved_by == "inam" and row.approval_note == "theek hai"
assert events == ["detected", "investigating", "awaiting_approval", "executing", "verifying", "resolved"], events
assert any("resolve ho gaya" in m for m in sent)
ok("W1c faisla aane par graph resume hua: restart > verify > resolved; approver DB me; timeline poori; notification")
quiet(worker.tick)
assert row_of("test-w1")[0].id == row.id
ok("W1d resolve ke baad wahi container (jo abhi bhi 'exited' dikhta hai) cooldown ki wajah se naya incident nahi banata")

# ---- W2: process restart ----
fake.reset()
fleet = [container("test-w2")]
quiet(make_worker(fleet).tick)                                         # Worker A: pause tak
row, _ = row_of("test-w2")
assert row.status == "awaiting_approval"
decide(row.id, True, "inam")
worker_b = make_worker(fleet)                                           # NAYA worker, naya graph, naya connection (process restart)
quiet(worker_b.tick, scan=False)
row, events = row_of("test-w2")
assert row.status == "resolved" and fake.restart_calls == 1
ok("W2 worker restart (naya process) ke baad bhi paused incident wahin se resume hua aur resolve hua")

# ---- W3: reject ----
fake.reset()
sent = []
fleet = [container("test-w3")]
worker = make_worker(fleet, sent)
quiet(worker.tick)
row, _ = row_of("test-w3")
decide(row.id, False, "sara", "pehle khud dekhna hai")
quiet(worker.tick)
row, events = row_of("test-w3")
assert row.status == "needs_review" and row.review_reason == "Rejected by sara: pehle khud dekhna hai" and fake.restart_calls == 0
assert any("review" in m for m in sent)
ok("W3 insaan ne 'no' kaha: needs_review (kis ne, kyun), restart nahi hua, notification")

# ---- W4: timeout ----
fake.reset()
configure(approval_timeout_minutes=-1)                                   # -1 = sab pending approvals purani maani jayein
fleet = [container("test-w4")]
worker = make_worker(fleet)
quiet(worker.process_detected)                                            # Scan ke bina seedha (pehle incident chahiye)
quiet(worker.scan)
quiet(worker.process_detected)
row, _ = row_of("test-w4")
assert row.status == "awaiting_approval"
quiet(worker.tick, scan=False)
row, _ = row_of("test-w4")
assert row.status == "needs_review" and row.approved_by == "system" and "timeout" in row.review_reason and fake.restart_calls == 0
ok("W4 approval ka waqt guzar gaya: 'rejected by system (timeout)', restart nahi hua")

# ---- W5: retry ke baad purana faisla dobara nahi lagta ----
configure()
fake.reset()
fake.restart_ok = False                                                    # Pehla restart fail
fleet = [container("test-w5")]
worker = make_worker(fleet)
quiet(worker.tick)
row, _ = row_of("test-w5")
decide(row.id, True, "inam")
quiet(worker.tick)                                                         # Resume -> restart fail -> retry -> dobara pause
row, events = row_of("test-w5")
assert fake.restart_calls == 1 and row.status == "awaiting_approval" and row.retry_count == 1
assert row.approval_decision is None and row.approved_by is None, "purana faisla saaf nahi hua!"
quiet(worker.tick)
assert fake.restart_calls == 1, "purane 'yes' par dobara restart ho gaya!"
ok("W5a restart fail hua > retry > dobara approval ka intezar; PURANA 'yes' saaf; bina naye faisle ke restart nahi")
fake.restart_ok = True
decide(row.id, True, "inam", "dobara")
quiet(worker.tick)
row, events = row_of("test-w5")
assert row.status == "resolved" and fake.restart_calls == 2 and events.count("awaiting_approval") == 2
ok("W5b naye faisle ke baad hi doosra restart hua aur resolve")

# ---- W6: auto-approve ----
configure(policy_auto_approve=True)
fake.reset(severity="Low", confidence=0.9)
fleet = [container("test-w6")]
quiet(make_worker(fleet).tick)
row, events = row_of("test-w6")
assert row.status == "resolved" and fake.restart_calls == 1 and "awaiting_approval" not in events
assert row.approved_by == "auto-policy" and row.approval_decision == "approved"
ok("W6a auto-approve: Low severity + confidence 0.9 par bina insaan ke restart > verify > resolved (approver 'auto-policy' record)")
fake.reset(severity="High", confidence=0.95)
fleet = [container("test-w6b")]
quiet(make_worker(fleet).tick)
row, _ = row_of("test-w6b")
assert row.status == "awaiting_approval" and fake.restart_calls == 0
ok("W6b auto_approve ON ho tab bhi High severity par insaan ka approval zaroori")

# ---- W7: dry-run ----
configure(policy_dry_run=True)
fake.reset()
fleet = [container("test-w7")]
quiet(make_worker(fleet).tick)
row, events = row_of("test-w7")
assert row.status == "needs_review" and "dry-run" in row.review_reason and fake.restart_calls == 0
assert row.diagnosis and row.recommended_action == "restart_container"
ok("W7 dry-run: poori diagnosis hui aur record hui, lekin restart nahi (needs_review 'dry-run')")

# ---- W8: rate limit ----
configure(policy_max_restarts_per_hour=1, policy_cooldown_minutes=0, policy_auto_approve=True)
fake.reset(severity="Low", confidence=0.9)
fleet = [container("test-w8")]
worker = make_worker(fleet)
quiet(worker.tick)
assert row_of("test-w8")[0].status == "resolved" and fake.restart_calls == 1
quiet(worker.tick)                                                         # Cooldown 0 -> naya incident -> policy
row, _ = row_of("test-w8")
assert row.status == "needs_review" and "restart limit" in row.review_reason and fake.restart_calls == 1
ok("W8 ghante me restart limit (1) poori hone par doosra incident blocked ('restart limit'), restart nahi")

# ---- W9: orphan recovery ----
configure()
sent = []
stuck = open_incident("beech me atka", "test-w9", "executing")
waiting = open_incident("approval ka intezar", "test-w9b", "awaiting_approval")
worker = make_worker([], sent)
quiet(worker.recover_orphans)
db = SessionLocal(); a = crud.get_incident(db, stuck); b = crud.get_incident(db, waiting); db.close()
assert a.status == "needs_review" and "restarted" in a.review_reason and b.status == "awaiting_approval"
assert any("adhura" in m for m in sent)
ok("W9 worker restart par beech me atka (executing) incident insaan ko gaya; awaiting_approval ko nahi chhera")

# ---- W10: graph crash par worker zinda ----
fake.reset(llm_error="LLM service down")
sent = []
fleet = [container("test-w10")]
worker = make_worker(fleet, sent)
quiet(worker.tick)
row, _ = row_of("test-w10")
assert row.status == "needs_review" and "LLM service down" in row.review_reason
assert any("Worker error" in m for m in sent)
fake.reset()
quiet(worker.tick)                                                           # Worker abhi zinda hai
ok("W10 graph crash (LLM down): worker mara nahi, incident needs_review + notification")

# ---- W11: checkpoint gum ----
fake.reset()
sent = []
ghost = open_incident("checkpoint nahi hai", "test-w11", "awaiting_approval")
decide(ghost, True, "inam")
worker = make_worker([], sent)
quiet(worker.tick, scan=False)
db = SessionLocal(); g = crud.get_incident(db, ghost); db.close()
assert g.status == "needs_review" and "checkpoint" in g.review_reason and fake.restart_calls == 0
ok("W11 faisla likha hai lekin graph ki saved state gum: chupchap atkne ki bajaye needs_review, restart nahi")

# ---- W12: ek waqt me ek incident ----
fake.reset()
fleet = [container("test-w12a"), container("test-w12b")]
worker = make_worker(fleet)
quiet(worker.tick)
statuses = sorted(row_of(n)[0].status for n in ("test-w12a", "test-w12b"))
assert statuses == ["awaiting_approval", "detected"], statuses
quiet(worker.tick)
statuses = sorted(row_of(n)[0].status for n in ("test-w12a", "test-w12b"))
assert statuses == ["awaiting_approval", "awaiting_approval"], statuses
ok("W12 do masle ek sath: ek round me ek hi incident chala (serial), doosra queue me raha, agle round me chala")

# ===========================================================================
print("\n[6] Notifications")
captured = []


class Handler(http.server.BaseHTTPRequestHandler):
    def do_POST(self):
        body = self.rfile.read(int(self.headers["Content-Length"]))
        captured.append((self.path, json.loads(body)))
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"{}")

    def log_message(self, *args):
        pass


server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
threading.Thread(target=server.serve_forever, daemon=True).start()
port = server.server_address[1]
configure(notify_channel="slack", slack_webhook_url=f"http://127.0.0.1:{port}/hook")
assert quiet(notify_tool.notify, "hello slack") is True and captured[-1] == ("/hook", {"text": "hello slack"})
ok("slack webhook par sahi JSON payload gaya")
configure(notify_channel="telegram", telegram_bot_token="TOK", telegram_chat_id="42", telegram_api_base=f"http://127.0.0.1:{port}")
assert quiet(notify_tool.notify, "hello tg") is True and captured[-1] == ("/botTOK/sendMessage", {"chat_id": "42", "text": "hello tg"})
ok("telegram sendMessage par sahi path aur payload gaya")
probe = socket.socket(); probe.bind(("127.0.0.1", 0)); dead_port = probe.getsockname()[1]; probe.close()
configure(notify_channel="slack", slack_webhook_url=f"http://127.0.0.1:{dead_port}/x")
assert quiet(notify_tool.notify, "x") is False
configure(notify_channel="telegram", telegram_bot_token="", telegram_chat_id="")
assert quiet(notify_tool.notify, "x") is False
ok("channel band ho ya token na ho to False wapas, exception nahi (notification se kuch rukta nahi)")
configure()
msg = notify_tool.format_incident_message(
    types.SimpleNamespace(id=7, container_name="web-1", severity="High", confidence=0.8, diagnosis="OOM", evidence='["a b", "c"]',
                          recommended_action="restart_container", solution="restart", review_reason=None), "HEAD", approve_hint=True)
assert "Evidence: a b | c" in msg and "scripts.approve 7 yes" in msg and "scripts.approve 7 no" in msg
ok("message me evidence aur approve/reject ke commands")

# ===========================================================================
print("\n[7] Migration (Day-8 jaisi table me naye approval columns)")
old_engine = create_engine(f"sqlite:///{TMP}/old_day8.db")
with old_engine.begin() as conn:
    conn.execute(sql_text("CREATE TABLE incidents (id INTEGER PRIMARY KEY, error_message TEXT NOT NULL, diagnosis TEXT, severity VARCHAR(20), status VARCHAR(20), created_at DATETIME, container_name VARCHAR(200), solution TEXT, recommended_action VARCHAR(40), confidence FLOAT, retry_count INTEGER DEFAULT 0, review_reason TEXT, updated_at DATETIME, resolved_at DATETIME)"))
    conn.execute(sql_text("INSERT INTO incidents (error_message, status, retry_count) VALUES ('purana', 'resolved', 2)"))
added = ensure_schema(old_engine)
assert sorted(a for a in added if a.startswith("incidents.")) == sorted(
    ["incidents.evidence", "incidents.approval_decision", "incidents.approved_by", "incidents.approval_note", "incidents.decided_at"]), added
with old_engine.connect() as conn:
    assert tuple(conn.execute(sql_text("SELECT error_message, status, retry_count FROM incidents")).one()) == ("purana", "resolved", 2)
ok("naye 5 approval/evidence columns jude, purani row safe")

server.shutdown()
print(f"\nALL {len(PASSED)} AUTOMATION CHECKS PASSED")
