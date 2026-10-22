# test_api.py
#
# OFFLINE tests (Day 12): FastAPI ke har rule (auth, validation, 403/404/409, CORS) aur asli END-TO-END:
#   API se incident banao -> WORKER diagnose karke approval par ruke -> API se approve -> worker resume
#   -> API me "resolved". LLM aur Docker fake hain; API, database, worker, checkpointer asli hain.
#
# Run (backend folder se):   python -m tests.test_api

import os                                                          # os - paths aur environment
import sys                                                         # sys - import path
import io                                                          # io - stdout capture
import tempfile                                                    # tempfile - temporary folder
import contextlib                                                  # contextlib - stdout capture

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # backend folder
sys.path.insert(0, BACKEND)                                         # "app" import ke liye
TMP = tempfile.mkdtemp()                                            # Temporary folder
os.chdir(TMP)                                                       # logs/ yahin banega
os.environ["GROQ_API_KEY"] = "dummy"
os.environ["GROQ_MODEL"] = "test-model"
os.environ["DATABASE_URL"] = os.environ.get("TEST_DATABASE_URL", f"sqlite:///{TMP}/api.db")
os.environ["FAISS_INDEX_PATH"] = f"{TMP}/idx.bin"
os.environ["CHECKPOINT_PATH"] = f"{TMP}/cp.sqlite"
for _name in ["POLICY_ALLOWED_CONTAINERS", "POLICY_DRY_RUN", "POLICY_AUTO_APPROVE", "NOTIFY_CHANNEL", "API_KEY",
              "API_CORS_ORIGINS", "POLICY_MAX_RESTARTS_PER_HOUR", "POLICY_COOLDOWN_MINUTES", "APPROVAL_TIMEOUT_MINUTES"]:
    os.environ.pop(_name, None)                                      # Shell ki settings se alag

from tests.fakes import Fake, install                                # Fake LLM/Docker
fake = Fake()
install(fake)                                                         # Asli modules me laga do

from fastapi.testclient import TestClient                            # FastAPI ka test client
from app.config import get_settings                                   # Settings (tests me badli jaati hain)
from app.db.database import SessionLocal                               # DB session
from app.db import crud                                                 # CRUD
from app.db.incidents import set_status                                 # Status badalne ke liye
from app.db.migrate import ensure_schema                                # Migration
from app.main import create_app                                          # App factory
import app.api.routes_health as routes_health                            # Health route (DB down test ke liye)
from app.agents.checkpointing import get_checkpointer                    # Checkpointer
from app.agents.graph import build_graph                                  # Graph
from app.worker.runner import Worker                                       # Worker

ensure_schema()                                                       # Temporary DB tayyar
SETTINGS = get_settings()
KEY = "test-secret-key-123"                                           # Test ki API key
H = {"X-API-Key": KEY}                                                 # Sahi header
PASSED = []


def ok(name):
    PASSED.append(name)
    print(f"  PASS: {name}")


def configure(**overrides):
    """Settings defaults par la kar overrides lagata hai."""
    defaults = dict(api_key=KEY, api_cors_origins="", policy_allowed_containers="test-*", policy_max_restarts_per_hour=100,
                    policy_cooldown_minutes=10, policy_dry_run=False, policy_auto_approve=False,
                    approval_timeout_minutes=30, notify_channel="console")
    defaults.update(overrides)
    for key, value in defaults.items():
        setattr(SETTINGS, key, value)


def drain_queue():
    """Pichle adhure incidents ko needs_review kar do (worker ki queue saaf)."""
    db = SessionLocal()
    try:
        for status in ("detected", "awaiting_approval", "investigating", "executing", "verifying"):
            for leftover in crud.list_by_status(db, status, 500):
                leftover.status = "needs_review"
        db.commit()
    finally:
        db.close()


def quiet(func, *args, **kwargs):
    with contextlib.redirect_stdout(io.StringIO()):
        return func(*args, **kwargs)


configure()
client = TestClient(create_app())                                      # Asli app, asli database


def create(container, message="the container keeps crashing again", expect=201):
    r = client.post("/incidents", json={"container_name": container, "error_message": message}, headers=H)
    assert r.status_code == expect, (r.status_code, r.text)
    return r.json()


# ===========================================================================
print("\n[1] Auth aur health")
configure(api_key="")
assert client.get("/incidents", headers=H).status_code == 503 and client.get("/incidents").status_code == 503
ok("API_KEY server par set na ho to sab endpoints 503 (khuli API nahi banti, fail-closed)")
configure()
assert client.get("/incidents").status_code == 401
assert client.get("/incidents", headers={"X-API-Key": "galat"}).status_code == 401
assert client.get("/incidents", headers={"X-API-Key": KEY + "x"}).status_code == 401
r = client.get("/incidents", headers=H)
assert r.status_code == 200 and isinstance(r.json(), list)
assert KEY not in client.get("/incidents", headers={"X-API-Key": "galat"}).text
ok("key missing/galat/lambi = 401, sahi = 200; jawab me asli key kabhi nahi dikhti")
for method, path in [("get", "/incidents/1"), ("post", "/incidents/1/approve"), ("post", "/incidents/1/reject")]:
    assert getattr(client, method)(path).status_code == 401, path
ok("detail, approve, reject sab par bhi key zaroori (bina key 401)")
r = client.get("/health")
assert r.status_code == 200 and r.json() == {"status": "ok", "database": "ok"}
ok("/health bina key ke chalta hai aur database ka haal batata hai")
saved_session = routes_health.SessionLocal


def broken_session():
    raise RuntimeError("database down")


routes_health.SessionLocal = broken_session
r = client.get("/health")
routes_health.SessionLocal = saved_session
assert r.status_code == 503 and r.json()["database"] == "error"
ok("database band ho to /health 503 'degraded' (monitoring ko pata chale)")

# ===========================================================================
print("\n[2] Incident banana (POST /incidents)")
created = create("test-a1")
assert created["status"] == "detected" and created["container_name"] == "test-a1" and created["id"] > 0
detail = client.get(f"/incidents/{created['id']}", headers=H).json()
assert [e["status"] for e in detail["events"]] == ["detected"] and detail["events"][0]["note"] == "manual trigger via API"
ok("201: incident 'detected' status me queue hua, timeline me 'manual trigger via API'")
dup = client.post("/incidents", json={"container_name": "test-a1", "error_message": "phir se kharab ho gaya"}, headers=H)
assert dup.status_code == 409 and f"#{created['id']}" in dup.json()["detail"]
ok("409: isi container ka incident pehle se chal raha ho to doosra nahi banta (dedupe)")
r = client.post("/incidents", json={"container_name": "prod-api", "error_message": "kuch kharab hai yahan"}, headers=H)
assert r.status_code == 403 and "allowlist" in r.json()["detail"]
r = client.post("/incidents", json={"container_name": "test-postgres", "error_message": "kuch kharab hai yahan"}, headers=H)
assert r.status_code == 403 and "protected" in r.json()["detail"]
ok("403: allowlist ke bahar ka container, aur allowlist me hote hue bhi protected (postgres) container")
for bad in [{"container_name": "bad name!", "error_message": "kuch kharab hai yahan"},
            {"container_name": "-startswithdash", "error_message": "kuch kharab hai yahan"},
            {"container_name": "a" * 201, "error_message": "kuch kharab hai yahan"},
            {"container_name": "test-v1", "error_message": "abc"},
            {"container_name": "test-v1"}, {"error_message": "kuch kharab hai yahan"}, {}]:
    assert client.post("/incidents", json=bad, headers=H).status_code == 422, bad
ok("422: galat container naam (space, !, dash se shuru, 201+ chars), chhota/missing error_message, khali body")
configure(policy_allowed_containers="")
assert create("anything-1")["status"] == "detected"
configure()
ok("allowlist khali ho to manual trigger par koi rok nahi (manual graph runs jaisa); protected phir bhi blocked")

# ===========================================================================
print("\n[3] List aur detail")
b = create("test-b1")
c = create("test-b2")
rows = client.get("/incidents", headers=H).json()
ids = [r["id"] for r in rows]
assert ids == sorted(ids, reverse=True) and c["id"] in ids
ok("list naye pehle")
assert all(r["status"] == "detected" for r in client.get("/incidents?status=detected", headers=H).json())
assert [r["container_name"] for r in client.get("/incidents?container=test-b1", headers=H).json()] == ["test-b1"]
page1 = client.get("/incidents?limit=1", headers=H).json()
page2 = client.get("/incidents?limit=1&offset=1", headers=H).json()
assert len(page1) == 1 and len(page2) == 1 and page1[0]["id"] != page2[0]["id"]
ok("status filter, container filter, limit/offset se pages")
for bad_query in ["status=bogus", "limit=0", "limit=201", "offset=-1"]:
    assert client.get(f"/incidents?{bad_query}", headers=H).status_code == 422, bad_query
ok("422: unknown status, limit 0 ya 201, negative offset")
assert client.get("/incidents/999999", headers=H).status_code == 404
assert client.get("/incidents/abc", headers=H).status_code == 422
ok("detail: anjaan ID par 404, number na ho to 422")

# ===========================================================================
print("\n[4] Approve / reject (database me faisla)")
inc = create("test-d1")
r = client.post(f"/incidents/{inc['id']}/approve", json={"by": "inam"}, headers=H)
assert r.status_code == 409 and "intezar nahi" in r.json()["detail"]
ok("awaiting_approval na ho to approve 409")
set_status(inc["id"], "awaiting_approval", None, diagnosis="OOM", severity="High")
r = client.post(f"/incidents/{inc['id']}/approve", json={"by": "inam", "note": "theek hai"}, headers=H)
body = r.json()
assert r.status_code == 200 and body["incident"]["approval_decision"] == "approved"
assert body["incident"]["approved_by"] == "inam" and body["incident"]["approval_note"] == "theek hai" and body["incident"]["decided_at"]
ok("200: approve - faisla, kis ne, note aur waqt database me")
assert client.post(f"/incidents/{inc['id']}/approve", json={"by": "sara"}, headers=H).status_code == 409
assert client.post(f"/incidents/{inc['id']}/reject", json={"by": "sara"}, headers=H).status_code == 409
assert client.get(f"/incidents/{inc['id']}", headers=H).json()["approved_by"] == "inam"
ok("409: ek incident par faisla sirf ek dafa; doosri koshish (approve ya reject) pehla faisla nahi badalti")
inc2 = create("test-d2")
set_status(inc2["id"], "awaiting_approval")
r = client.post(f"/incidents/{inc2['id']}/reject", headers=H)
assert r.status_code == 200 and r.json()["incident"]["approval_decision"] == "rejected" and r.json()["incident"]["approved_by"] == "api"
ok("reject bina body ke bhi chalta hai (by default 'api')")
assert client.post("/incidents/999999/approve", headers=H).status_code == 404
assert client.post(f"/incidents/{inc2['id']}/approve", json={"by": "x" * 101}, headers=H).status_code == 422
inc3 = create("test-d3")
set_status(inc3["id"], "awaiting_approval")
assert client.post(f"/incidents/{inc3['id']}/approve", json={"note": "n" * 501}, headers=H).status_code == 422
assert client.post(f"/incidents/{inc3['id']}/approve", json={"by": ""}, headers=H).status_code == 422
assert client.get(f"/incidents/{inc3['id']}", headers=H).json()["approval_decision"] is None
ok("404 anjaan ID; 422 lamba/khali 'by', lamba note - aur galat input par faisla likha hi nahi gaya")

# ===========================================================================
print("\n[5] END-TO-END: API -> worker -> API (asli graph, asli checkpointer)")
configure()
drain_queue()
fake.reset()
sent = []
worker = Worker(build_graph(get_checkpointer("sqlite", os.environ["CHECKPOINT_PATH"])), list_containers=lambda: [], notify_fn=sent.append)

item = create("test-e2e1", "test-e2e1 keeps crashing and requests fail")
quiet(worker.tick, scan=False)
view = client.get(f"/incidents/{item['id']}", headers=H).json()
assert view["status"] == "awaiting_approval" and fake.restart_calls == 0
assert view["recommended_action"] == "restart_container" and view["confidence"] == 0.8 and view["severity"] == "High"
assert view["evidence"] == ["out of memory: killed process 42"] and "ran out of memory" in view["diagnosis"]
assert any(f"scripts.approve {item['id']} yes" in m for m in sent)
ok("E1 API se banaya > worker ne diagnose kiya > API me 'awaiting_approval', diagnosis, evidence (list), action, confidence; restart nahi hua")
dup = client.post("/incidents", json={"container_name": "test-e2e1", "error_message": "phir kharab hai"}, headers=H)
assert dup.status_code == 409
ok("E2 jab tak incident approval par ruka hai, usi container ka naya incident 409")
r = client.post(f"/incidents/{item['id']}/approve", json={"by": "inam", "note": "api se"}, headers=H)
assert r.status_code == 200
quiet(worker.tick, scan=False)
view = client.get(f"/incidents/{item['id']}", headers=H).json()
assert view["status"] == "resolved" and view["approved_by"] == "inam" and view["resolved_at"] and fake.restart_calls == 1
assert [e["status"] for e in view["events"]] == ["detected", "investigating", "awaiting_approval", "executing", "verifying", "resolved"], view["events"]
ok("E3 API se approve > worker ne resume kiya > API me 'resolved', approver 'inam', poora timeline, ek hi restart")

item2 = create("test-e2e2", "test-e2e2 keeps crashing and requests fail")
quiet(worker.tick, scan=False)
r = client.post(f"/incidents/{item2['id']}/reject", json={"by": "sara", "note": "pehle logs dekhne hain"}, headers=H)
assert r.status_code == 200
before = fake.restart_calls
quiet(worker.tick, scan=False)
view = client.get(f"/incidents/{item2['id']}", headers=H).json()
assert view["status"] == "needs_review" and view["review_reason"] == "Rejected by sara: pehle logs dekhne hain"
assert fake.restart_calls == before
ok("E4 API se reject > worker ne resume kiya > 'needs_review', wajah 'Rejected by sara: ...', restart nahi hua")

# ===========================================================================
print("\n[6] CORS (frontend ke liye)")
preflight = {"Origin": "http://localhost:3000", "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "X-API-Key"}
assert "access-control-allow-origin" not in TestClient(create_app()).options("/incidents", headers=preflight).headers
ok("CORS default band: koi origin allowed nahi")
configure(api_cors_origins="http://localhost:3000, https://dash.example.com")
cors_client = TestClient(create_app())
r = cors_client.options("/incidents", headers=preflight)
assert r.status_code == 200 and r.headers.get("access-control-allow-origin") == "http://localhost:3000"
assert "x-api-key" in r.headers.get("access-control-allow-headers", "").lower()
r = cors_client.options("/incidents", headers={**preflight, "Origin": "http://evil.example"})
assert r.headers.get("access-control-allow-origin") is None
configure()
ok("CORS ON: sirf configured origins ko ijazat (localhost:3000), doosre (evil.example) ko nahi, X-API-Key header allowed")

print(f"\nALL {len(PASSED)} API CHECKS PASSED")
