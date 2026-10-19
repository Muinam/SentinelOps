# runner.py
#
# Is file ka kaam: WORKER - wo ek process jo sab kuch jodta hai:
#   1) Docker scan karta hai (watcher) aur naye masle "detected" status me queue karta hai
#   2) "detected" incident par graph chalata hai (diagnosis -> critic -> solution -> policy)
#   3) Graph approval par ruk jaye to insaan ko NOTIFY karta hai
#   4) Insaan ka faisla DB me aaye (scripts/approve.py) to graph RESUME karta hai
#   5) Approval ka waqt guzar jaye to incident insaan ko (needs_review)
# Safety: ek waqt me ek incident (serial); graph crash kare to worker nahi marta;
# restart par beech me atke incidents insaan ko bheje jaate hain (dobara chalaye nahi jaate).
#
# Chalane ka tareeqa (backend folder se):
#   python -m app.worker            # hamesha chalta rahe
#   python -m app.worker --once     # ek round chala kar ruk jaye (test/cron ke liye)
# NOTE: ek waqt me sirf EK worker chalayein.

import argparse                                                   # argparse - command line options
import time                                                        # time - poll ke beech sleep
from app.config import get_settings                                # .env ki settings
from app.agents.graph import build_graph, RECURSION_LIMIT          # Graph (worker mode) aur step limit
from app.agents.checkpointing import get_checkpointer              # Pause/resume ki state ki file
from app.core.guardrails import load_policy                         # Policy rules
from app.db.database import SessionLocal                            # DB session
from app.db import crud                                              # Incident queries
from app.db.incidents import set_status                              # Best-effort status update
from app.db.migrate import ensure_schema                             # Database tayyar karna
from app.tools.notify_tool import notify, format_incident_message    # Insaan ko batana
from app.watcher.docker_watcher import scan_once, list_docker_containers   # Docker scan


class Worker:
    """Ek worker. Testing ke liye graph, Docker list aur notify bahar se diye ja sakte hain."""

    def __init__(self, graph, list_containers=None, notify_fn=None):
        self.graph = graph                                          # Worker mode me compile hua graph (checkpointer ke sath)
        self.list_containers = list_containers or list_docker_containers   # Docker se containers ki list
        self.notify = notify_fn or notify                            # Notification bhejne wala
        self._warned_allowlist = False                                # Khali allowlist ki warning ek hi baar

    # ------------------------------------------------------------------ chhote helpers
    def _config(self, incident_id: int) -> dict:
        """Har incident ka apna thread_id - isi se checkpointer uski state dhoondta hai."""
        return {"configurable": {"thread_id": str(incident_id)}, "recursion_limit": RECURSION_LIMIT}

    def _fetch(self, incident_id: int):
        """Incident row padhta hai (session band karne ke baad bhi attributes padhe ja sakte hain)."""
        db = SessionLocal()
        try:
            return crud.get_incident(db, incident_id)
        finally:
            db.close()

    def _after_run(self, incident_id: int, config: dict) -> None:
        """Graph ke chalne ya ruknay ke baad insaan ko batao: ruka (approval chahiye) ya khatam."""
        snapshot = self.graph.get_state(config)                       # Graph ki maujooda halat
        row = self._fetch(incident_id)
        if snapshot.next:                                              # Abhi kuch baaki hai = approval par ruka hua
            self.notify(format_incident_message(row, "🔔 Approval chahiye", approve_hint=True))
        elif row.status == "resolved":
            self.notify(format_incident_message(row, "✅ Incident resolve ho gaya"))
        else:
            self.notify(format_incident_message(row, "⚠️ Insaan ko review karna hai"))

    def _invoke(self, incident_id: int, graph_input, decision=None) -> None:
        """
        Graph chalata (graph_input=state) ya resume karta (graph_input=None, decision=(approved, by, note)) hai.
        Koi bhi exception worker ko nahi marti - incident needs_review ho jata hai.
        """
        config = self._config(incident_id)
        try:
            if decision is not None:                                    # Resume: pehle saved state check karo
                if not self.graph.get_state(config).next:                  # Kuch ruka hua nahi - checkpoint gum
                    raise RuntimeError("graph ki saved state nahi mili (checkpoint missing)")
                approved, by, note = decision
                self.graph.update_state(config, {                            # Faisla graph ki state me bharo
                    "approved": approved, "approval_decided": True, "approved_by": by, "approval_note": note or "",
                })
            self.graph.invoke(graph_input, config)                           # Chalao / resume karo
        except Exception as error:                                          # LLM down, checkpoint gum, koi bug...
            print(f"[WORKER] ❌ incident #{incident_id} par graph fail: {error}")
            set_status(incident_id, "needs_review", "worker error", review_reason=f"Worker error: {error}")
            self.notify(format_incident_message(self._fetch(incident_id), "⚠️ Worker error - insaan dekhe"))
            return
        self._after_run(incident_id, config)

    # ------------------------------------------------------------------ worker ke kaam
    def scan(self) -> list:
        """Docker scan: naye masle "detected" status me queue karta hai."""
        policy = load_policy()
        if not policy.allowed_patterns:                                    # Allowlist khali - scan nahi
            if not self._warned_allowlist:
                print("[WORKER] POLICY_ALLOWED_CONTAINERS khali hai - Docker scan band. .env me daalein, jaise: POLICY_ALLOWED_CONTAINERS=test-nginx")
                self._warned_allowlist = True
            return []
        return scan_once(self.list_containers(), policy, get_settings().watch_ignore_clean_exit)

    def process_detected(self, limit: int = 1) -> None:
        """Queue ke purane "detected" incidents par graph chalata hai (ek waqt me limit tak)."""
        db = SessionLocal()
        try:
            ids = [row.id for row in crud.list_by_status(db, "detected", limit)]
        finally:
            db.close()
        for incident_id in ids:
            row = self._fetch(incident_id)
            state = {"error_message": row.error_message, "container_name": row.container_name, "incident_id": row.id}
            print(f"[WORKER] incident #{incident_id} par graph chal raha hai...")
            self._invoke(incident_id, state)

    def process_decisions(self) -> None:
        """Jin awaiting_approval incidents par faisla ho chuka hai, unka graph resume karta hai."""
        db = SessionLocal()
        try:
            ready = [
                (row.id, row.approval_decision == "approved", row.approved_by, row.approval_note)
                for row in crud.list_by_status(db, "awaiting_approval", 50)
                if row.approval_decision                                      # Faisla likha ja chuka hai
            ]
        finally:
            db.close()
        for incident_id, approved, by, note in ready:
            print(f"[WORKER] incident #{incident_id} resume ({'approved' if approved else 'rejected'} by {by})")
            self._invoke(incident_id, None, decision=(approved, by, note))

    def expire_stale(self) -> None:
        """Jin approvals ka waqt guzar gaya, unko "rejected by system" likh deta hai (process_decisions unhe resume karega)."""
        minutes = get_settings().approval_timeout_minutes
        db = SessionLocal()
        try:
            for row in crud.list_stale_awaiting(db, minutes):
                crud.record_decision(db, row.id, False, "system", f"approval {minutes} minute me nahi mila (timeout)")
                print(f"[WORKER] incident #{row.id} ka approval timeout")
        finally:
            db.close()

    def recover_orphans(self) -> None:
        """
        Worker start par: jo incidents beech me atke hain (investigating/executing/verifying) unko insaan ko bhejo.
        Dobara chalate nahi - beech me rukne ke baad container ki halat anjaan hai, restart khatarnak ho sakta hai.
        (awaiting_approval aur detected ko chhedte nahi - wo checkpoint/queue se wapas chalenge.)
        """
        db = SessionLocal()
        try:
            orphans = [row.id for status in ("investigating", "executing", "verifying")
                       for row in crud.list_by_status(db, status, 50)]
        finally:
            db.close()
        for incident_id in orphans:
            set_status(incident_id, "needs_review", "worker restarted",
                       review_reason="Worker restarted while this incident was in progress; please review it manually.")
            self.notify(format_incident_message(self._fetch(incident_id), "⚠️ Worker restart ke waqt ye incident adhura tha"))
            print(f"[WORKER] adhura incident #{incident_id} insaan ko bheja gaya")

    # ------------------------------------------------------------------ loop
    def _phase(self, name: str, func) -> None:
        """Ek phase chalata hai; error aaye to print kar ke aage badhta hai (worker nahi marta)."""
        try:
            func()
        except Exception as error:
            print(f"[WORKER] ⚠️ {name} me error (worker chalta rahega): {error}")

    def tick(self, scan: bool = True) -> None:
        """Ek round: expire -> decisions resume -> scan -> naya incident chalao."""
        self._phase("expire", self.expire_stale)
        self._phase("decisions", self.process_decisions)
        if scan:
            self._phase("scan", self.scan)
        self._phase("detected", self.process_detected)

    def run_forever(self, poll_seconds: int, scan: bool = True) -> None:
        """Hamesha chalta rahta hai, har poll_seconds baad ek tick. Ctrl+C se band."""
        try:
            while True:
                self.tick(scan)
                time.sleep(poll_seconds)
        except KeyboardInterrupt:
            print("\n[WORKER] band kiya gaya.")


def main(argv=None) -> None:
    parser = argparse.ArgumentParser(description="SentinelOps worker")
    parser.add_argument("--once", action="store_true", help="ek round chala kar ruk jao")
    parser.add_argument("--no-scan", action="store_true", help="Docker scan na karo (sirf queue aur approvals)")
    parser.add_argument("--poll", type=int, default=None, help="har kitne second baad check (default .env se)")
    args = parser.parse_args(argv)

    settings = get_settings()
    policy = load_policy()
    print("=" * 60)
    print("SentinelOps worker")
    print(f"  allowlist      : {', '.join(policy.allowed_patterns) or '(khali - Docker scan band)'}")
    print(f"  dry-run        : {policy.dry_run}   auto-approve: {policy.auto_approve}")
    print(f"  max restarts/hr: {policy.max_restarts_per_hour}   cooldown: {policy.cooldown_minutes} min")
    print(f"  approval timeout: {settings.approval_timeout_minutes} min   notify: {settings.notify_channel}")
    print("=" * 60)

    ensure_schema()                                                        # Database tayyar (dobara chalane par kuch nahi badalta)
    worker = Worker(build_graph(get_checkpointer("sqlite")))                # Worker mode ka graph
    worker.recover_orphans()                                                 # Beech me atke incidents
    if args.once:
        worker.tick(scan=not args.no_scan)
    else:
        worker.run_forever(args.poll or settings.worker_poll_seconds, scan=not args.no_scan)
