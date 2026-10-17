import json                                                    # json - payload banane aur incident ka evidence padhne ke liye
import urllib.request                                          # urllib - HTTP POST ke liye (built-in)
from app.config import get_settings                            # .env ki settings

MAX_CHARS = 3500                                                # Telegram ki limit 4096 hai, thora kam rakha


def _post_json(url: str, payload: dict, timeout: int = 10) -> None:
    """Ek JSON POST bhejta hai. Fail ho to exception uthata hai (notify() usko pakadta hai)."""
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),                # Body JSON bytes me
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:   # Bhejo aur jawab ka intezar
        response.read()                                                    # Jawab padh lo (connection saaf)


def notify(text: str) -> bool:
    """
    Message bhejta hai. Console par hamesha print hota hai; telegram/slack settings ke hisab se.
    Return: True agar bhej diya (ya sirf console), False agar channel fail hua. KABHI raise nahi karta.
    """
    settings = get_settings()
    text = text[:MAX_CHARS]                                        # Lamba message kaat do
    print(f"[NOTIFY] {text}")                                       # Console par hamesha dikhao

    channel = settings.notify_channel.strip().lower()
    try:
        if channel == "telegram":
            if not (settings.telegram_bot_token and settings.telegram_chat_id):
                raise ValueError("TELEGRAM_BOT_TOKEN ya TELEGRAM_CHAT_ID .env me nahi hai")
            url = f"{settings.telegram_api_base}/bot{settings.telegram_bot_token}/sendMessage"
            _post_json(url, {"chat_id": settings.telegram_chat_id, "text": text})
        elif channel == "slack":
            if not settings.slack_webhook_url:
                raise ValueError("SLACK_WEBHOOK_URL .env me nahi hai")
            _post_json(settings.slack_webhook_url, {"text": text})
        return True                                                  # console ya kamyab channel
    except Exception as error:                                       # Notification ki wajah se kuch rukna nahi chahiye
        print(f"[NOTIFY] ⚠️ {channel} par message nahi gaya: {error}")
        return False


def format_incident_message(row, headline: str, approve_hint: bool = False) -> str:
    """Incident row se insaan ke parhne layak message banata hai."""
    lines = [
        headline,
        f"Incident #{row.id} | container: {row.container_name} | severity: {row.severity} | confidence: {row.confidence}",
    ]
    if row.diagnosis:
        lines.append(f"Diagnosis: {row.diagnosis}")
    if row.evidence:                                                  # JSON list ko line me badlo
        try:
            lines.append("Evidence: " + " | ".join(json.loads(row.evidence)))
        except (ValueError, TypeError):
            lines.append(f"Evidence: {row.evidence}")
    if row.recommended_action:
        lines.append(f"Action: {row.recommended_action} - {row.solution}")
    if row.review_reason:
        lines.append(f"Reason: {row.review_reason}")
    if approve_hint:                                                   # Insaan ko batao kaise faisla kare
        lines.append(f"Approve: python -m scripts.approve {row.id} yes   |   Reject: python -m scripts.approve {row.id} no")
    return "\n".join(lines)
