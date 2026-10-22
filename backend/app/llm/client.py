import time                                                    # time - latency napne aur sleep ke liye
import groq                                                    # groq - exception classes ke liye
from groq import Groq                                          # Groq ka official Python client
from app.config import get_settings                             # Hamara config loader
from app.core.logging import log_event                          # logs/agent.log me likhne ke liye

settings = get_settings()                                        # .env se GROQ_API_KEY, GROQ_MODEL waghera

# Groq client ek dafa banate hain, poore module me reuse hoga
_client = Groq(api_key=settings.groq_api_key)                    # Underscore _client = "internal use only" convention

_sleep = time.sleep                                              # Sleep ka alias - tests isko tez/fake kar dete hain

MAX_RETRY_AFTER = 30                                             # Server kitna bhi kahe, is se zyada nahi rukenge (second)

# Jin errors par SAME model par dobara koshish karna theek hai
RETRYABLE = (groq.RateLimitError, groq.APIConnectionError, groq.InternalServerError)
# Jin errors ka matlab "ye model yahan hai hi nahi" - retry bekaar, seedha agla model
MODEL_UNAVAILABLE = (groq.NotFoundError,)


def _model_chain() -> list:
    """Primary model, phir .env ke fallback models (duplicate hataa kar, order ke sath)."""
    chain = [settings.groq_model]                                  # Pehle primary
    for name in settings.groq_fallback_models.split(","):          # Comma se alag fallback naam
        name = name.strip()
        if name and name not in chain:                              # Khali ya duplicate nahi
            chain.append(name)
    return chain


def _wait_seconds(error, attempt: int) -> float:
    """Retry se pehle kitna ruknna hai: server ka Retry-After (agar diya ho), warna exponential backoff."""
    response = getattr(error, "response", None)                     # Error ke sath aaya HTTP response (agar ho)
    header = response.headers.get("retry-after") if response is not None else None
    if header:
        try:
            return min(float(header), MAX_RETRY_AFTER)               # Server ki marzi, lekin hadd me
        except ValueError:
            pass                                                      # Number nahi to backoff use karo
    return settings.llm_backoff_seconds * (2 ** attempt)             # 1.5s, 3s, 6s ...


def _log_success(model: str, attempt: int, started: float, response) -> None:
    """Kamyab call ka model, koshish number, latency aur tokens log me likhta hai."""
    try:
        usage = getattr(response, "usage", None)                      # Groq tokens ki ginti deta hai
        tokens = f"in={usage.prompt_tokens} out={usage.completion_tokens}" if usage else "in=? out=?"
        log_event(f"LLM | model={model} | attempt={attempt + 1} | {time.time() - started:.2f}s | tokens {tokens}")
    except Exception:
        pass                                                           # Log ki wajah se call kharab nahi honi chahiye


def call_llm(messages: list, tools: list | None = None, max_tokens: int = 1024):
    """
    LLM ko call karta hai (retry + fallback ke sath).

    Params:
        messages   - conversation history (OpenAI-style: role + content)
        tools      - optional tool/function schemas
        max_tokens - jawab ki max length (reasoning model me sochne ke tokens bhi ginte hain)

    Return: Groq ka raw response object. Sab models fail hon to aakhri error uthta hai.
    """
    kwargs = {"messages": messages, "max_tokens": max_tokens}      # Har model ke liye common arguments
    if tools:                                                        # tools/tool_choice sirf tab (Groq None accept nahi karta)
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    last_error = None                                                # Aakhri error (sab fail hon to wahi uthega)
    chain = _model_chain()                                           # [primary, fallback1, fallback2...]

    for position, model in enumerate(chain):                        # Ek ek model aazmao
        for attempt in range(max(0, settings.llm_max_retries) + 1):   # Is model par 1 + retries koshishen (negative ho to 1)
            started = time.time()
            try:
                response = _client.chat.completions.create(model=model, **kwargs)
                _log_success(model, attempt, started, response)
                return response                                      # Kamyab
            except MODEL_UNAVAILABLE as error:                      # Model hi nahi hai
                last_error = error
                print(f"[LLM] model '{model}' available nahi ({type(error).__name__}) - agla model")
                break                                                # Is model par retry bekaar
            except RETRYABLE as error:                               # Rate limit / network / server
                last_error = error
                if attempt < max(0, settings.llm_max_retries):       # Retry baaki hai
                    wait = _wait_seconds(error, attempt)
                    print(f"[LLM] '{model}' {type(error).__name__} - {wait:.1f}s baad dobara (koshish {attempt + 2})")
                    _sleep(wait)
                else:
                    print(f"[LLM] '{model}' par retries khatam ({type(error).__name__})")
        if position + 1 < len(chain):                                # Aur model baaki hai
            print(f"[LLM] fallback: '{chain[position + 1]}' par ja rahe hain")

    raise last_error                                                  # Sab models fail
