import json                                           # json - tool arguments parse karne aur observation banane ke liye
from app.llm.client import call_llm                   # Hamara LLM wrapper

MAX_OBSERVATION_CHARS = 3000                           # Tool ka nateeja is se lamba ho to sirf aakhri hissa rakho (logs ka aakhir zyada kaam ka hota hai)


def _short(text: str) -> str:
    """Lambe observation ko chhota karta hai - aakhri MAX_OBSERVATION_CHARS characters rakhta hai."""
    return text if len(text) <= MAX_OBSERVATION_CHARS else text[-MAX_OBSERVATION_CHARS:]


def run_react_loop(messages: list, tools: list, tool_map: dict, max_steps: int = 4):
    """
    ReAct loop chalata hai.

    Params:
        messages  - shuru ki conversation (system + user), ye list andar se badlegi
        tools     - LLM ko dikhane wale tool schemas
        tool_map  - {tool_ka_naam: python_function} - LLM ke maange tool ko chalane ke liye
        max_steps - zyada se zyada kitne tool-rounds (infinite loop se bachne ke liye)

    Return: (final_text, trace)
        final_text - LLM ka aakhri jawab (bina tool ke)
        trace      - har step ka record: [{"step", "tool", "args", "observation"}, ...]
    """
    trace = []                                           # Har step yahan record hoga

    for step in range(1, max_steps + 1):                 # Zyada se zyada max_steps rounds
        response = call_llm(messages=messages, tools=tools)    # LLM ko poochho: tool chahiye ya jawab ready hai?
        message = response.choices[0].message                    # LLM ka message

        if not message.tool_calls:                         # Koi tool nahi maanga -> LLM ka jawab tayyar hai
            return (message.content or ""), trace           # Final text aur trace wapas karo

        # ---- LLM ne tool maange: pehle uska message history me daalo (dict form me, portable) ----
        messages.append({
            "role": "assistant",
            "content": message.content or "",
            "tool_calls": [
                {
                    "id": call.id,                                   # Har tool call ki unique ID
                    "type": "function",
                    "function": {"name": call.function.name, "arguments": call.function.arguments},
                }
                for call in message.tool_calls
            ],
        })

        for call in message.tool_calls:                      # Har maange gaye tool ke liye
            name = call.function.name                          # Tool ka naam
            try:
                args = json.loads(call.function.arguments or "{}")   # Arguments JSON string se dict me
            except json.JSONDecodeError:
                args = {}                                             # Kharab arguments -> khali, tool khud error dega

            func = tool_map.get(name)                          # Naam se python function dhoondo
            if func is None:                                    # LLM ne aisa tool maanga jo hamare paas hai hi nahi
                result = {"error": f"unknown tool '{name}'"}
            else:
                try:
                    result = func(**args)                        # Tool chalao
                except Exception as error:                        # Tool crash ho to loop na tootay - error ko hi observation banao
                    result = {"error": f"tool failed: {error}"}

            observation = _short(json.dumps(result, default=str, ensure_ascii=False))  # Nateeja text me, chhota kar ke
            trace.append({"step": step, "tool": name, "args": args, "observation": observation})  # Record karo
            print(f"[REACT step {step}] tool={name} args={args}")       # Terminal par dikhao
            messages.append({"role": "tool", "tool_call_id": call.id, "content": observation})  # Observation LLM ko wapas

    # ---- Steps khatam, LLM ne abhi tak jawab nahi diya: bina tools ke ek aakhri jawab maango ----
    messages.append({"role": "user", "content": "Step limit reached. Summarize what you found so far in plain text."})
    final = call_llm(messages=messages)                       # Is baar tools nahi diye, to jawab dena hi padega
    return (final.choices[0].message.content or ""), trace
