from app.agents.state import AgentState
from app.llm.client import call_llm
from app.tools.rag_tool import search_similar_incidents

def diagnosis_node(state: AgentState) -> AgentState:
    """
    Steps:
    1. RAG se similar past incidents dhoondo (Day 2 ka tool, direct call - LLM tool-loop nahi)
    2. Error + system status + similar incidents - sab LLM ko ek sath do
    3. LLM se structured diagnosis + severity maango
    """
    print("[NODE] diagnosis_node running...")

    rag_result = search_similar_incidents(state['error_message'])
    
    retry_note=""
    if state.get('retry_count',0)>0:
        retry_note = (
            f"\nIMPORTANT: Pichli fix koshish FAIL hui. Nateeja: {state.get('execution_result')}. "
            f"Pichla diagnosis tha: {state.get('diagnosis')}. Dobara soch kar alag/behtar diagnosis dein.\n"
        )

    prompts=f"""
    Error: {state['error_message']}
    System status: {state['system_status']}
    Similar past incidents: {rag_result}
    {retry_note}

    Upar di gayi information ke basis par, is format me jawab do:
    ROOT_CAUSE: <ek line>
    SEVERITY: <Low/Medium/High/Critical>
    """

    messages=[
        {"role": "system", "content": 'Aap ed SRE diagnosi agent hain. Concise jawab dein. IMPORTANT: Hamesha respond in ENGLISH ONLY, chahe input kisi bhi language me ho.'},
        {"role": "user", "content": prompts},
    ]

    response = call_llm(messages=messages)
    text = response.choices[0].message.content
    

    # ---- Simple parsing - text se ROOT_CAUSE aur SEVERITY nikalo ----
    diagnosis = "Unknown"                                  # Default fallback value
    severity = "Medium"                                     # Default fallback value
    
    for line in text.splitlines():                         # Har line check karo
        if line.startswith("ROOT_CAUSE:"):
            diagnosis = line.replace("ROOT_CAUSE:", "").strip()
        elif line.startswith("SEVERITY:"):
            severity = line.replace("SEVERITY:", "").strip()

    return {
        'similar_incidents': rag_result.get('similar_incidents', []),
        'diagnosis' : diagnosis,
        'severity': severity
    }