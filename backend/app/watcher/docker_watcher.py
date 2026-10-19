# docker_watcher.py
#
# Is file ka kaam: Docker containers ko DEKHNA aur masla pakadna (khud-ba-khud detect).
# Do hisse (alag alag, taake test ho sakein):
#   detect_problem() - SAAF logic: container ki halat dekh kar batati hai ke masla hai ya nahi
#   scan_once()      - allowlist + dedupe + cooldown lagakar naya incident "detected" status me kholta hai
# Polling use ho rahi hai (har kuch second par check). Docker events stream ek behtar upgrade hai,
# lekin polling aasan aur kaafi hai.

from app.core.guardrails import Policy, is_allowed, is_protected   # Allowlist aur protected containers ke rules
from app.db.database import SessionLocal                            # DB session
from app.db import crud                                              # Incident queries


class WatcherConfigError(Exception):
    """Watcher ki settings galat/adhoori hain (jaise allowlist khali)."""


def describe_container(container) -> dict:
    """Docker SDK ke container object se zaroori halat nikalta hai (naam, status, exit code, health...)."""
    attrs = getattr(container, "attrs", None) or {}                  # Docker ka raw inspect data
    state = attrs.get("State", {}) or {}                              # State ka hissa
    health = (state.get("Health") or {}).get("Status")                 # Health check ka status (agar container me ho)
    return {
        "name": container.name,
        "status": getattr(container, "status", None) or state.get("Status"),   # running / exited / restarting ...
        "exit_code": state.get("ExitCode"),                              # Band hone par exit code
        "oom_killed": bool(state.get("OOMKilled")),                       # Memory khatam hone par kill hua?
        "restarting": bool(state.get("Restarting")),                       # Restart loop me hai?
        "health": health,                                                   # healthy / unhealthy / starting / None
        "restart_count": attrs.get("RestartCount", 0),                       # Docker ne kitni dafa restart kiya
    }


def detect_problem(info: dict, ignore_clean_exit: bool = False):
    """
    Container ki halat dekh kar masla batati hai. Return: masle ka chhota bayan (text), ya None agar sab theek hai.
    ignore_clean_exit=True ho to exit code 0 (saaf band hona) ko masla nahi maante.
    """
    status = info.get("status")
    if status == "restarting" or info.get("restarting"):                # Crash loop
        return f"container keeps restarting (restart count {info.get('restart_count', 0)})"
    if status in ("exited", "dead"):                                      # Band ho gaya
        code = info.get("exit_code")
        if code == 0 and ignore_clean_exit:                                  # Saaf band hona - masla nahi
            return None
        oom = " (OOMKilled: memory limit se kill hua)" if info.get("oom_killed") else ""
        return f"container {status} with exit code {code}{oom}"
    if info.get("health") == "unhealthy":                                  # Health check fail
        return "container health check is failing (unhealthy)"
    return None                                                              # Sab theek


def list_docker_containers():
    """Asli Docker se SAARE containers (band wale bhi). Docker band ho to exception uthti hai."""
    import docker                                                           # Yahin import - tests me Docker ke bina chale
    return docker.from_env().containers.list(all=True)


def scan_once(containers, policy: Policy, ignore_clean_exit: bool = False) -> list:
    """
    Containers ki list dekh kar naye masle pakadta hai aur har ek ke liye incident "detected" status me kholta hai.
    Return: [{"incident_id", "container", "problem"}, ...] - sirf naye incidents.
    Chhodta hai: allowlist ke bahar, protected (database/cache), pehle se active incident wala, cooldown wala.
    """
    if not policy.allowed_patterns:                                           # Allowlist khali - khud-ba-khud kaam khatarnak hai
        raise WatcherConfigError(
            "POLICY_ALLOWED_CONTAINERS khali hai. Watcher tab tak koi container nahi dekhega - .env me daalein, "
            "jaise: POLICY_ALLOWED_CONTAINERS=test-nginx"
        )

    opened = []                                                                 # Naye incidents
    db = SessionLocal()
    try:
        for container in containers:
            info = describe_container(container)
            name = info["name"]
            if not is_allowed(name, policy) or is_protected(name):               # Hamara scope nahi / protected
                continue
            problem = detect_problem(info, ignore_clean_exit)                      # Masla hai?
            if problem is None:
                continue

            if crud.find_active_incident(db, name) is not None:                    # Isi container ka incident pehle se chal raha hai
                continue
            if crud.in_cooldown(db, name, policy.cooldown_minutes):                  # Abhi abhi khatam hua - flapping se bacho
                print(f"[WATCHER] {name}: {problem} - cooldown ({policy.cooldown_minutes} min) chal raha hai, naya incident nahi")
                continue

            incident = crud.create_open_incident(db, f"{name}: {problem}", name, status="detected")   # Queue me daalo
            crud.add_event(db, incident.id, "detected", problem)
            print(f"[WATCHER] 🚨 incident #{incident.id}: {name}: {problem}")
            opened.append({"incident_id": incident.id, "container": name, "problem": problem})
    finally:
        db.close()
    return opened
