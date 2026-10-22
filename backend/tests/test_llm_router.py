# test_llm_router.py
#
# OFFLINE tests: LLM router (retry, backoff, Retry-After, fallback model, model gum, galat request,
# sab fail, logging). Groq ko KABHI call nahi karta - ek fake client chalata hai, lekin ASLI groq
# exception classes use karta hai. Temporary folder me chalta hai.
#
# Run (backend folder se):   python -m tests.test_llm_router

import os                                                          # os - paths aur environment
import sys                                                         # sys - import path
import io                                                          # io - stdout capture
import types                                                       # types - fake objects
import tempfile                                                    # tempfile - temporary folder
import contextlib                                                  # contextlib - stdout capture

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # backend folder
sys.path.insert(0, BACKEND)                                         # "app" import ke liye
TMP = tempfile.mkdtemp()                                            # Temporary folder
os.chdir(TMP)                                                       # logs/ yahin banega
os.environ["GROQ_API_KEY"] = "dummy"                                # Fake key
os.environ["GROQ_MODEL"] = "primary"                                # Fake model
os.environ["DATABASE_URL"] = f"sqlite:///{TMP}/router.db"          # Settings ko chahiye (use nahi hota)

import httpx                                                        # httpx - groq exceptions ke liye request/response
import groq                                                         # Asli groq exception classes
import app.llm.client as client                                     # Router
from app.config import get_settings                                  # Settings

SETTINGS = get_settings()                                            # Shared settings
PASSED = []                                                          # Pass hue checks
REQUEST = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")   # Fake request


def ok(name):
    PASSED.append(name)
    print(f"  PASS: {name}")


def status_error(cls, code, headers=None):
    """Asli groq status error (RateLimitError, NotFoundError...) banata hai."""
    response = httpx.Response(code, request=REQUEST, headers=headers or {})
    return cls("boom", response=response, body=None)


def success(text="ok", tokens=(10, 5)):
    """Groq response jaisa object (usage ke sath)."""
    message = types.SimpleNamespace(content=text, tool_calls=None)
    usage = types.SimpleNamespace(prompt_tokens=tokens[0], completion_tokens=tokens[1])
    return types.SimpleNamespace(choices=[types.SimpleNamespace(message=message)], usage=usage)


class FakeCompletions:
    """Har model ke liye scripted nateeje: list me Exception ya response. Aakhri item repeat hota hai."""

    def __init__(self, script):
        self.script = {model: list(items) for model, items in script.items()}   # model -> outcomes
        self.calls = []                                                          # [(model, kwargs)]

    def create(self, model, **kwargs):
        self.calls.append((model, kwargs))
        items = self.script[model]
        outcome = items.pop(0) if len(items) > 1 else items[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def setup(script, fallback="second,third", retries=2, backoff=1.5):
    """Router ko fake client aur fake sleep de kar tayyar karta hai. Return: (fake, sleeps)."""
    SETTINGS.groq_model = "primary"
    SETTINGS.groq_fallback_models = fallback
    SETTINGS.llm_max_retries = retries
    SETTINGS.llm_backoff_seconds = backoff
    fake = FakeCompletions(script)
    client._client = types.SimpleNamespace(chat=types.SimpleNamespace(completions=fake))
    sleeps = []
    client._sleep = sleeps.append                                         # Asli sleep nahi, sirf record
    return fake, sleeps


def call(**kwargs):
    """call_llm chalata hai (print dabata hai)."""
    with contextlib.redirect_stdout(io.StringIO()):
        return client.call_llm([{"role": "user", "content": "hi"}], **kwargs)


print("\n[1] Router ke raaste")

# ---- R1: pehli koshish kamyab ----
fake, sleeps = setup({"primary": [success("hello")]})
assert call().choices[0].message.content == "hello" and len(fake.calls) == 1 and sleeps == []
ok("R1 pehli koshish kamyab: ek call, koi intezar nahi")

# ---- R2: rate limit do baar, phir kamyab (same model, exponential backoff) ----
fake, sleeps = setup({"primary": [status_error(groq.RateLimitError, 429), status_error(groq.RateLimitError, 429), success()]})
call()
assert [m for m, _ in fake.calls] == ["primary"] * 3 and sleeps == [1.5, 3.0], (fake.calls, sleeps)
ok("R2 429 par same model par dobara: intezar 1.5s phir 3.0s (double), 3rd koshish kamyab")

# ---- R3: retries khatam -> fallback model ----
fake, sleeps = setup({"primary": [status_error(groq.RateLimitError, 429)], "second": [success("from second")]})
assert call().choices[0].message.content == "from second"
assert [m for m, _ in fake.calls] == ["primary", "primary", "primary", "second"] and sleeps == [1.5, 3.0]
ok("R3 primary par 3 koshishon ke baad 429 raha to 'second' model par chala gaya aur kamyab")

# ---- R4: model gum (404) -> seedha agla, retry nahi ----
fake, sleeps = setup({"primary": [status_error(groq.NotFoundError, 404)], "second": [success("second ok")]})
call()
assert [m for m, _ in fake.calls] == ["primary", "second"] and sleeps == []
ok("R4 model gum (404, jaise deprecate hua model): retry/intezar ke bina seedha agla model")

# ---- R5: sab models fail -> aakhri error ----
fake, sleeps = setup({m: [status_error(groq.RateLimitError, 429)] for m in ("primary", "second", "third")})
try:
    call()
    raise SystemExit("FAIL: error nahi aaya")
except groq.RateLimitError:
    pass
assert len(fake.calls) == 9
ok("R5 teeno models (3-3 koshish) fail: aakhri RateLimitError upar (9 calls, atakta nahi)")

# ---- R6: galat request / galat key -> fauran upar, fallback nahi ----
for cls, code in [(groq.BadRequestError, 400), (groq.AuthenticationError, 401)]:
    fake, sleeps = setup({"primary": [status_error(cls, code)], "second": [success()]})
    try:
        call()
        raise SystemExit("FAIL: error nahi aaya")
    except cls:
        pass
    assert len(fake.calls) == 1 and sleeps == []
ok("R6 galat request (400) ya galat API key (401): fauran upar, fallback/retry nahi (wo theek nahi karenge)")

# ---- R7: Retry-After header ----
fake, sleeps = setup({"primary": [status_error(groq.RateLimitError, 429, {"retry-after": "2"}), success()]})
call()
assert sleeps == [2.0]
fake, sleeps = setup({"primary": [status_error(groq.RateLimitError, 429, {"retry-after": "9999"}), success()]})
call()
assert sleeps == [30.0]
fake, sleeps = setup({"primary": [status_error(groq.RateLimitError, 429, {"retry-after": "soon"}), success()]})
call()
assert sleeps == [1.5]
ok("R7 Retry-After maana jata hai (2s), 30s se zyada nahi rukta (9999 -> 30), number na ho to backoff")

# ---- R8: network aur server errors ----
fake, sleeps = setup({"primary": [groq.APIConnectionError(request=REQUEST), status_error(groq.InternalServerError, 503), success()]})
call()
assert len(fake.calls) == 3 and len(sleeps) == 2
ok("R8 network error aur 503 server error par retry")

# ---- R9: fallback chain ----
fake, sleeps = setup({"primary": [status_error(groq.NotFoundError, 404)]}, fallback="")
try:
    call()
    raise SystemExit("FAIL")
except groq.NotFoundError:
    pass
assert [m for m, _ in fake.calls] == ["primary"]
ok("R9a fallback khali ho to sirf primary (aur uska error upar)")
SETTINGS.groq_fallback_models = " primary , second ,second,, third "
assert client._model_chain() == ["primary", "second", "third"]
ok("R9b fallback list saaf hoti hai: spaces, duplicate aur khali naam hat jate hain")

# ---- R10: tools aur max_tokens sahi jaate hain ----
fake, sleeps = setup({"primary": [success()]})
call(tools=[{"type": "function"}], max_tokens=2048)
sent = fake.calls[0][1]
assert sent["max_tokens"] == 2048 and sent["tool_choice"] == "auto" and sent["tools"] == [{"type": "function"}]
fake, sleeps = setup({"primary": [success()]})
call()
sent = fake.calls[0][1]
assert "tools" not in sent and "tool_choice" not in sent and sent["max_tokens"] == 1024
ok("R10 tools ho to tool_choice=auto; na ho to dono keys hi nahi (Groq None accept nahi karta); max_tokens pass hota hai")

# ---- R11: negative retries ----
fake, sleeps = setup({"primary": [status_error(groq.RateLimitError, 429)], "second": [success()]}, retries=-1)
call()
assert [m for m, _ in fake.calls] == ["primary", "second"] and sleeps == []
ok("R11 retries negative ho tab bhi crash nahi (1 koshish, phir fallback)")

# ---- R12: logging ----
fake, sleeps = setup({"primary": [status_error(groq.RateLimitError, 429), success(tokens=(123, 45))]})
call()
with open(os.path.join("logs", "agent.log"), encoding="utf-8") as handle:
    log_text = handle.read()
assert "LLM | model=primary | attempt=2" in log_text and "tokens in=123 out=45" in log_text, log_text
ok("R12 logs/agent.log me model, koshish number, latency aur tokens (in=123 out=45) likhe gaye")
setup({"primary": [types.SimpleNamespace(choices=[], usage=None)]})
call()
ok("R12b usage na ho to bhi logging crash nahi karti")

print(f"\nALL {len(PASSED)} ROUTER CHECKS PASSED")
