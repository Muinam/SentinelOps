# client.py
#
# Is file ka MAQSAD: Groq API call ko ek jagah "wrap" karna.
# Poore project me koi bhi file "Groq" ka naam seedha nahi lega - sab is file ke
# through call karenge. Isse jab hum LLM ROUTER add karenge (jo Groq, ya kisi
# doosre free/open-source provider ke beech switch kare), sirf yehi file badlegi.

from groq import Groq                          # Groq ka official Python client
from app.config import get_settings             # Hamara config loader

settings = get_settings()                        # .env se GROQ_API_KEY, GROQ_MODEL uthao

# Groq client ek dafa banate hain, poore module me reuse hoga
_client = Groq(api_key=settings.groq_api_key)    # Underscore _client = "internal use only" convention


def call_llm(messages: list, tools: list | None = None, max_tokens: int = 1024):
    """
    Ye function LLM ko call karta hai - abhi Groq (open-source Llama) use ho raha hai.

    Params:
        messages - conversation history (OpenAI-style format: role + content)
        tools    - optional list of tool/function schemas
        max_tokens - jawab ki max length (reasoning model me sochne ke tokens bhi isme ginte hain,
                     isliye JSON jaise lambe jawab ke liye bada rakhein, jaise 2048)

    Return:
        Groq ka raw response object (jaisa OpenAI-compatible APIs dete hain)

    IMPORTANT (future): jab LLM router aayega, is function ke ANDAR ka code
    badlega (e.g. provider select karne ka logic) - lekin is function ka
    naam aur signature (messages, tools) SAME rahega, taake baaki code me
    kahin bhi change na karna pare.
    """

    # ---- kwargs ek dictionary hai jisme hum call ke arguments jama karenge ----
    # Isse hum "tools"/"tool_choice" ko sirf TAB add karenge jab tools diye gaye hon
    kwargs = {
        "model": settings.groq_model,            # .env se aaya model naam
        "messages": messages,                     # Conversation history
        "max_tokens": max_tokens,                 # Response ki max length (ab parameter se aati hai)
    }

    if tools:                                       # Sirf agar tools di gayi hon
        kwargs["tools"] = tools                       # Tools list add karo
        kwargs["tool_choice"] = "auto"                 # LLM khud decide kare kab tool use kare
    # Agar tools None/empty hain, to "tools" aur "tool_choice" dono KEYS hi nahi bhejenge
    # (Groq None value accept nahi karta - key ka missing hona hi sahi tareeqa hai)

    response = _client.chat.completions.create(**kwargs)  # ** se dictionary ko arguments me unpack karo

    return response                                          # Poora response object wapas bhejo
