# day7_test_hardened.py
#
# ASLI run (Groq + Docker chahiye): structured output + ReAct + critic + verify wala poora graph.
#
# PEHLE offline tests chalayein (bina Groq/Docker ke, 30 second):
#   python -m tests.test_hardening
#
# Phir ye script, 2 scenarios ke liye:
#   A) Container THEEK hai, error message jhoota ("unresponsive"):
#        docker start test-nginx      (ya: docker run -d --name test-nginx nginx)
#        python -m scripts.day7_test_hardened
#      Umeed: critic/diagnosis "No fault found" kehta hai, koi restart nahi.
#   B) Container sach me band hai:
#        docker stop test-nginx
#        python -m scripts.day7_test_hardened
#      Umeed: fault mila -> approval -> restart -> verify -> reporter (incident save).

import sys                                                        # sys - import path ke liye
import os                                                         # os - path banane ke liye
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))    # "app" folder import ke liye add karo

from app.agents.graph import compiled_graph, RECURSION_LIMIT      # Graph aur uski step limit
from app.rag.ingest import backfill_from_postgres                 # Postgres -> FAISS (memory khali ho to)
from app.db.migrate import ensure_schema                          # Day 8: purani table me naye columns jodta hai

CONTAINER_NAME = "test-nginx"                                      # Sirf test container! Airflow/postgres/redis nahi


def main():
    ensure_schema()                                                # Day 8: database ko lifecycle ke liye tayyar karo (dobara chalane par kuch nahi badalta)
    backfill_from_postgres()                                       # RAG memory khali ho to Postgres se bharo

    initial_state = {                                              # Sirf input fields; baaki nodes khud bharte hain
        "error_message": f"{CONTAINER_NAME} container unresponsive hai aur requests fail ho rahi hain",
        "container_name": CONTAINER_NAME,
    }

    print("=" * 60)
    print("Running Day 7 HARDENED Graph (ReAct + JSON + critic + verify)...")
    print("=" * 60)

    final = compiled_graph.invoke(initial_state, {"recursion_limit": RECURSION_LIMIT})   # Poora graph chalao

    print("\n" + "=" * 60)
    print("RESULT")
    print("=" * 60)
    print(f"fault_found      : {final.get('fault_found')}")
    print(f"diagnosis        : {final.get('diagnosis')}")
    print(f"severity         : {final.get('severity')}   confidence: {final.get('confidence')}")
    print(f"evidence         : {final.get('diagnosis_evidence')}")
    print(f"critic_supported : {final.get('critic_supported')}   reflections: {final.get('reflection_count')}")
    print(f"action           : {final.get('recommended_action')}")
    print(f"approved/verified: {final.get('approved')} / {final.get('verified')}")
    print(f"retry_count      : {final.get('retry_count')}")
    print(f"incident_id      : {final.get('incident_id')}")
    print(f"review_reason    : {final.get('review_reason')}")
    print("ReAct steps      :")
    for step in final.get("react_trace", []):                       # LLM ne khud kaunse tools chune
        print(f"   {step['step']}. {step['tool']} {step['args']}")
    print("\nNode timings: logs/agent.log")
    print(f"Incident ka timeline: python -m scripts.show_incident {final.get('incident_id')}")


if __name__ == "__main__":
    main()
