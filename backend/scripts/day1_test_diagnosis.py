# day1_test_diagnosis.py
#
# DAY 1 - MORNING TASK (updated to use Groq - free, open-source LLMs)
# Goal: Samajhna ke "tool/function calling" kaam kaise karta hai.
# Yahan hum LLM ko ek DUMMY tool dete hain (check_system_status) - abhi ye
# real Docker/DB se connect nahi hai, sirf concept samajhne ke liye hai.
#
# Run karne ka tareeqa (terminal se):
#   cd backend
#   pip install -r requirements.txt
#   python -m scripts.day1_test_diagnosis

import sys                                        # sys - path manipulation ke liye
import os                                         # os - file paths handle karne ke liye
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # "app" folder ko import path me add karo

from app.llm.client import call_llm                # Hamara LLM wrapper (abhi Groq, kal router)
from app.agents.prompts.diagnosis_prompt import DIAGNOSIS_SYSTEM_PROMPT  # System prompt import

import json                                          # json - tool arguments parse karne ke liye


# ---- STEP 1: Dummy tool ka ACTUAL Python function ----
# Ye function wahi hai jo LLM "call" karne ki request karega
# Abhi ye fake/mock data return kar raha hai - Day 4 me ye real Docker se connect hoga
def check_system_status(service_name: str) -> dict:
    """
    Dummy function - normally ye Docker/GCP se real status fetch karta
    Abhi hum sirf tool-calling ka FLOW samajh rahe hain, isliye fake data return kar rahe hain
    """
    return {
        "service": service_name,           # Jis service ka status poocha gaya
        "status": "unhealthy",             # Fake status - production me real check hoga
        "cpu_usage": "92%",                # Fake CPU usage
        "restart_count_last_hour": 4,      # Fake restart count - suspicious pattern
    }


# ---- STEP 2: Tool ka SCHEMA define karo (Groq/OpenAI-style format) ----
# Ye schema LLM ko batata hai: "ye tool exist karta hai, isse ye inputs chahiye"
# NOTE: format Anthropic se thora different hai - "type": "function" wrapper hai
tools = [
    {
        "type": "function",                          # Groq/OpenAI-style: har tool "function" type ka hota hai
        "function": {
            "name": "check_system_status",            # Tool ka naam (function name se match hona chahiye)
            "description": (                            # LLM isi text se samjhega tool kab use karna hai
                "Check the live health status, CPU usage, and recent restart count "
                "of a given service/container. Use this whenever you need real-time "
                "system data instead of guessing."
            ),
            "parameters": {                             # Tool ko kaunsa input chahiye, uska schema
                "type": "object",
                "properties": {
                    "service_name": {                   # Ek hi parameter: service ka naam
                        "type": "string",
                        "description": "Name of the service or container to check",
                    }
                },
                "required": ["service_name"],           # Ye field zaroori hai, optional nahi
            },
        },
    }
]


def run_diagnosis(error_message: str) -> str:
    """
    Ye function poora tool-calling LOOP demonstrate karta hai:
    1. System prompt + user error LLM ko bhejo
    2. Agar LLM tool call karna chahe, to hum Python me wo function chalayein
    3. Result wapas LLM ko dein
    4. LLM final human-readable diagnosis de
    """

    # OpenAI/Groq-style me system prompt bhi messages list ke andar ek "role" hota hai
    messages = [
        {"role": "system", "content": DIAGNOSIS_SYSTEM_PROMPT},          # Agent ka role/instructions
        {"role": "user", "content": f"Production error aaya hai: {error_message}"},  # User ka error
    ]

    # ---- Pehli LLM call: error + available tools batao ----
    response = call_llm(messages=messages, tools=tools)    # Hamara wrapper function (app/llm/client.py)

    message = response.choices[0].message                   # Groq ka response is path par milta hai

    # ---- STEP 3: Check karo - kya LLM ne tool call maanga? ----
    # Groq/OpenAI format me ye "message.tool_calls" ke andar aata hai (list, khali ho sakti hai)
    if message.tool_calls:

        # LLM ka poora message conversation history me add karo (context ke liye zaroori)
        messages.append(message)

        for tool_call in message.tool_calls:                 # Har tool call ke liye loop (usually 1 hoti hai)
            tool_name = tool_call.function.name               # Kaunsa tool call hua
            tool_args = json.loads(tool_call.function.arguments)  # Arguments string se dict me convert

            print(f"[TOOL CALL] {tool_name} with input: {tool_args}")  # Debug ke liye print

            # ---- STEP 4: Actual Python function chalao ----
            if tool_name == "check_system_status":
                result = check_system_status(**tool_args)     # ** se dict ko arguments me unpack karo
            else:
                result = {"error": "Unknown tool requested"}    # Safety fallback

            # ---- STEP 5: Tool ka result LLM ko wapas bhejo ----
            # Groq/OpenAI format me ye role "tool" ke sath jaata hai, tool_call_id match karte hue
            messages.append(
                {
                    "role": "tool",                            # "tool" role - result LLM ko batata hai
                    "tool_call_id": tool_call.id,               # Kaunsi call ka jawab hai (ID match)
                    "content": str(result),                     # Result ko string me convert kiya
                }
            )

        # ---- STEP 6: Doosri LLM call - ab final diagnosis milega ----
        final_response = call_llm(messages=messages, tools=tools)  # Ab isme tool result bhi shamil hai
        return final_response.choices[0].message.content            # Final text nikal kar return karo

    # Agar LLM ne tool call nahi kiya, to direct text response return karo
    return message.content


# ---- STEP 7: Script ko directly run karne par test karo ----
if __name__ == "__main__":
    # Ek sample error jo humara agent diagnose karega
    sample_error = "payment-service container baar baar crash ho raha hai, 502 errors aa rahe hain"

    print("=" * 60)                              # Sirf readability ke liye separator line
    print("Running Day 1 Diagnosis Test (Groq)...")
    print("=" * 60)

    diagnosis = run_diagnosis(sample_error)      # Hamara main function call karo

    print("\nFINAL DIAGNOSIS:\n")
    print(diagnosis)                              # LLM ka final structured diagnosis print karo
