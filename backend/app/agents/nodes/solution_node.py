# solution_node.py
#
# Graph ka SOLUTION node. Ab ye sirf text nahi likhta - ek ACTION CHUNTA hai (structured JSON):
#   "restart_container"    -> hamara automated action, approval ke baad executor chalayega
#   "manual_intervention"  -> restart is masle ka ilaaj nahi, insaan ko karna hoga
# Isse "approve kiya kuch aur, chala kuch aur" wala masla khatam hota hai.

from app.agents.state import AgentState                      # State ka shape
from app.agents.schemas import SolutionPlan                  # Validated schema
from app.llm.structured import call_llm_json, StructuredOutputError  # JSON + validation helper


def solution_node(state: AgentState) -> AgentState:
    print("[NODE] solution_node running...")

    system_text = (
        "You are a senior SRE choosing a remediation. The ONLY automated action available is "
        "'restart_container'. Choose it only if a restart can plausibly fix the diagnosed root cause "
        "(for example a hung process or a transient crash). If the cause needs a configuration change, "
        "a code fix, more resources or human judgement, choose 'manual_intervention' and explain what the "
        "human should do. Do not claim to run any other action. Reply in English."
    )
    user_text = (
        f"Diagnosis: {state.get('diagnosis')}\n"
        f"Severity: {state.get('severity')}\n"
        f"Evidence: {state.get('diagnosis_evidence')}\n"
        f"Similar past incidents: {state.get('similar_incidents', [])}\n"
    )
    try:
        plan = call_llm_json(
            [{"role": "system", "content": system_text}, {"role": "user", "content": user_text}],
            SolutionPlan,
        )
    except StructuredOutputError as error:                     # LLM valid plan na de paya
        print(f"[SOLUTION] structured output fail: {error}")
        return {                                                # Safe side: insaan ke paas bhejo
            "solution": "",
            "recommended_action": "manual_intervention",
            "review_reason": "A remediation plan could not be produced automatically.",
        }

    update = {"solution": plan.explanation, "recommended_action": plan.action}   # Validated nateeja
    if plan.action != "restart_container":                      # Automated action nahi hai
        update["review_reason"] = f"Manual intervention needed: {plan.explanation}"
    return update
