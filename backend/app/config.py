# config.py
# Is file ka kaam: environment variables (.env file) ko ek clean Python object me load karna
# Fayda: har jagah os.getenv() likhne ke bajaye, "settings.anthropic_api_key" jaisa clean access milta hai

from pydantic_settings import BaseSettings   # BaseSettings - .env se auto values uthata hai
from pydantic import Field                    # Field - default values aur validation ke liye
from functools import lru_cache                # lru_cache - settings ko baar baar load hone se bachata hai


class Settings(BaseSettings):
    """
    Ye class hamari poori app ki configuration define karti hai.
    Har attribute automatically .env file ya system environment se match ho kar fill hota hai.
    """

    # Groq API key - free/open-source LLMs (Llama etc.) call karne ke liye zaroori
    # Field(...) ka matlab ye required hai, agar .env me na mile to error aayega
    groq_api_key: str = Field(..., description="Groq API key (free tier)")

    # Kaunsa open-source model use karna hai - default value di hai agar .env me na likha ho
    # NOTE: aage chal kar isko ek "LLM router" replace kar dega jo automatically
    # best/available open-source model choose karega (multiple providers ke beech)
    groq_model: str = Field(
        default="openai/gpt-oss-120b",
        description="Which open-source model to use via Groq",
    )

    # FAISS index file kahan save/load hoga disk par
    faiss_index_path: str = Field(
        default="./data/faiss_index.bin",
        description="Path to the saved FAISS vector index file",
    )

    # Postgres/Supabase connection string
    database_url: str = Field(..., description="Postgres connection string (Supabase)")

    # ------------------------------------------------------------------
    # Day 9-11 NAYE settings - sab ke DEFAULT hain, .env badle bina purana flow chalta hai
    # ------------------------------------------------------------------

    # ---- Policy / guardrails (core/guardrails.py) ----
    # Kaunse containers par agent kaam kare - comma se alag naam ya pattern (jaise: test-nginx,web-*)
    # KHALI = manual run par koi rok nahi, lekin WATCHER (khud-ba-khud) tab tak shuru nahi hoga jab tak ye na bharein
    policy_allowed_containers: str = Field(default="", description="Comma separated names/patterns")
    policy_max_restarts_per_hour: int = Field(default=3, description="Ek container ke liye ghante me zyada se zyada restarts")
    policy_cooldown_minutes: int = Field(default=10, description="Incident khatam hone ke baad itni der naya incident nahi (dedupe)")
    policy_dry_run: bool = Field(default=False, description="True = diagnose aur notify, lekin koi restart nahi")
    policy_auto_approve: bool = Field(default=False, description="True = low-risk restarts bina insaan ke approve")
    policy_auto_approve_max_severity: str = Field(default="Medium", description="Auto-approve ke liye sab se bari severity")
    policy_auto_approve_min_confidence: float = Field(default=0.8, description="Auto-approve ke liye kam az kam confidence")

    # ---- Approval aur worker ----
    approval_timeout_minutes: int = Field(default=30, description="Itni der approval na mile to incident insaan ko (needs_review)")
    worker_poll_seconds: int = Field(default=10, description="Worker har kitne second baad check kare")
    watch_ignore_clean_exit: bool = Field(default=False, description="True = exit code 0 ko masla na samjho")
    checkpoint_path: str = Field(default="./data/checkpoints.sqlite", description="Graph ke pause/resume ki state ki file")

    # ---- Notifications (tools/notify_tool.py) ----
    notify_channel: str = Field(default="console", description="console | telegram | slack")
    telegram_bot_token: str = Field(default="", description="Telegram bot token (BotFather se, free)")
    telegram_chat_id: str = Field(default="", description="Telegram chat ID")
    telegram_api_base: str = Field(default="https://api.telegram.org", description="Sirf testing ke liye badalte hain")
    slack_webhook_url: str = Field(default="", description="Slack incoming webhook URL (free)")

    class Config:
        # Pydantic ko batata hai ke values ".env" naam ki file se uthani hain
        env_file = ".env"
        # Agar .env me extra unused variables hon to error na de
        extra = "ignore"


@lru_cache()  # Decorator - is function ka result ek dafa compute ho ga, phir cache se milega
def get_settings() -> Settings:
    """
    Settings object ko lazily (jab zaroorat ho tab) banata hai aur cache karta hai.
    Poore app me hum isi function ko call karenge settings access karne ke liye.
    """
    return Settings()  # .env file read kar ke Settings object return karta hai
