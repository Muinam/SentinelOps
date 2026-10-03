from groq import Groq
from app.config import get_settings

settings = get_settings()

# Groq client ek dafa banate hain, poore module me reuse hoga
_client = Groq(api_key=settings.groq_api_key)    # Underscore _client = "internal use only" convention


def call_llm(messages:list, tools:list |None = None):
    """
    Ye function LLM ko call karta hai - abhi Groq (open-source Llama) use ho raha hai.

    Params:
        messages - conversation history (OpenAI-style format: role + content)
        tools    - optional list of tool/function schemas

    Return:
        Groq ka raw response object (jaisa OpenAI-compatible APIs dete hain)

    IMPORTANT (future): jab LLM router aayega, is function ke ANDAR ka code
    badlega (e.g. provider select karne ka logic) - lekin is function ka
    naam aur signature (messages, tools) SAME rahega, taake baaki code me
    kahin bhi change na karna pare.
    """

    kwargs = {
        "model": settings.groq_model,            # .env se aaya model naam
        "messages": messages,                     # Conversation history
        "max_tokens": 1024,                       # Response ki max length
    }


    if tools:                                       # Sirf agar tools di gayi hon
        kwargs["tools"] = tools                       # Tools list add karo
        kwargs["tool_choice"] = "auto" 
    # Groq ka chat completion call - ye OpenAI ke format se compatible hai
    response = _client.chat.completions.create(**kwargs)


    return response