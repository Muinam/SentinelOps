from app.agents import prompts
from app.agents.state import AgentState
from app.llm.client import call_llm

def solution_node(state: AgentState):
    """
    Pichle node se mile diagnosis ko lekar, ek actionable solution maangta hai.
    """
    print("[NODE] solution_node running...")

    prompt = f"""
    Diagnosis: {state['diagnosis']}
    Severity: {state['severity']}
    Similar past fixes: {state['similar_incidents']}

    Ek CONCRETE, actionable fix suggest karo (1-2 lines, specific steps).
    """

    messages = [
        {"role": "system", "content": "Aap ek SRE solution agent hain. Short, actionable fix dein. IMPORTANT: Hamesha respond in ENGLISH ONLY, chahe input kisi bhi language me ho."},
        {"role": "user", "content": prompt},
    ]

    response = call_llm(messages=messages)             # Simple LLM call, koi tool nahi chahiye yahan
    solution_text = response.choices[0].message.content   # Text nikal lo

    return {"solution": solution_text}