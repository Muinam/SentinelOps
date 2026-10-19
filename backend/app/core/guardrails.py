# guardrails.py
#
# Is file ka kaam: "kya agent ko is container par kaam karne diya jaye?" ka FAISLA - ek hi jagah.
# Ye saaf logic hai (database ke bina test ho sakti hai): allowlist, protected containers,
# ghante ki restart limit, dry-run aur auto-approve ke rules.
#
# Faisle 3 tarah ke hote hain:
#   "blocked" - action nahi hoga, incident insaan ke paas (wajah ke sath)
#   "auto"    - policy ne khud approve kiya, seedha executor
#   "human"   - insaan ke approval ka intezar

from dataclasses import dataclass                       # dataclass - chhoti data class banane ka aasan tareeqa
from fnmatch import fnmatch                              # fnmatch - "web-*" jaise patterns match karne ke liye
from app.config import get_settings                      # .env ki settings
from app.tools.docker_tool import PROTECTED_KEYWORDS     # postgres/redis jaise protected naam (docker_tool ka wahi rule)

SEVERITY_RANK = {"Low": 0, "Medium": 1, "High": 2, "Critical": 3}   # Severity ka order (chhoti se bari)


@dataclass
class Policy:
    """Saare rules ek jagah (settings se banta hai)."""
    allowed_patterns: tuple              # Allowed container naam/patterns (khali = koi rok nahi)
    max_restarts_per_hour: int           # Ek container par ghante me zyada se zyada restarts
    cooldown_minutes: int                # Incident ke baad itni der naya incident nahi
    dry_run: bool                        # True = koi restart nahi
    auto_approve: bool                   # True = low-risk restarts khud approve
    auto_approve_max_severity: str       # Auto-approve ke liye sab se bari severity
    auto_approve_min_confidence: float   # Auto-approve ke liye kam az kam confidence


@dataclass
class Decision:
    """Policy ka faisla: kind (blocked/auto/human) aur wajah."""
    kind: str
    reason: str


def load_policy() -> Policy:
    """Settings se Policy banata hai. Har dafa taaza padhta hai (testing me settings badli ja sakti hain)."""
    settings = get_settings()
    patterns = tuple(p.strip() for p in settings.policy_allowed_containers.split(",") if p.strip())   # Comma se todo, khali hatao
    return Policy(
        allowed_patterns=patterns,
        max_restarts_per_hour=settings.policy_max_restarts_per_hour,
        cooldown_minutes=settings.policy_cooldown_minutes,
        dry_run=settings.policy_dry_run,
        auto_approve=settings.policy_auto_approve,
        auto_approve_max_severity=settings.policy_auto_approve_max_severity,
        auto_approve_min_confidence=settings.policy_auto_approve_min_confidence,
    )


def is_allowed(container: str, policy: Policy) -> bool:
    """Container allowlist me hai? Allowlist khali ho to True (manual run par koi rok nahi)."""
    if not policy.allowed_patterns:
        return True
    name = container.lower()
    return any(fnmatch(name, pattern.lower()) for pattern in policy.allowed_patterns)


def is_protected(container: str) -> bool:
    """Database/cache jaise protected container? (naam me postgres, redis... ho)"""
    name = container.lower()
    return any(keyword in name for keyword in PROTECTED_KEYWORDS)


def evaluate_action(policy: Policy, container: str, severity: str, confidence, critic_supported: bool,
                    action: str, retry_count: int, recent_restarts) -> Decision:
    """
    Restart se pehle faisla. recent_restarts: ghante me kitne restarts hue (None = pata nahi, DB masla).
    Rules ka order: allowlist -> protected -> rate limit -> dry-run -> auto-approve -> human.
    """
    if not is_allowed(container, policy):                          # 1) Allowlist
        return Decision("blocked", f"container '{container}' allowlist me nahi hai")
    if is_protected(container):                                     # 2) Protected (database/cache)
        return Decision("blocked", f"'{container}' protected container hai (database/cache), agent isko restart nahi karega")
    if recent_restarts is not None and recent_restarts >= policy.max_restarts_per_hour:   # 3) Rate limit
        return Decision("blocked", f"restart limit khatam: pichle ghante me {recent_restarts} restarts (max {policy.max_restarts_per_hour})")
    if policy.dry_run:                                               # 4) Dry-run
        return Decision("blocked", "dry-run mode: restart nahi hoga (policy)")

    # 5) Auto-approve - sab shartein poori honi chahiye, aur recent_restarts maloom hona chahiye
    rank = SEVERITY_RANK.get(severity, 99)                           # Unknown severity = bahut bari (auto nahi)
    max_rank = SEVERITY_RANK.get(policy.auto_approve_max_severity, -1)
    if (policy.auto_approve and action == "restart_container" and critic_supported
            and recent_restarts is not None and retry_count == 0
            and rank <= max_rank and (confidence or 0) >= policy.auto_approve_min_confidence):
        return Decision("auto", f"low-risk: severity {severity}, confidence {confidence}, restarts/hour {recent_restarts}")

    return Decision("human", "insaan ka approval chahiye")           # 6) Baaki sab - insaan
