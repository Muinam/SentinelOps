
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.agents.graph import compiled_graph
from app.rag.ingest import backfill_from_postgres      # Postgres -> FAISS (memory khali ho to)

CONTAINER_NAME = "test-nginx"       # <-- Sirf test container! Airflow/postgres/redis wale naam mat do


def main():
    # ---- STEP 1: RAG memory ko REAL data se bharo (Postgres ki history se) ----
    # Ye sirf tab kuch karega jab FAISS memory khali ho (pehli dafa). Baad me skip hota hai.
    backfill_from_postgres()

    # ---- STEP 2: Saare state fields ke default values ke sath shuru karo ----
    initial_state = {
        "error_message": f"{CONTAINER_NAME} container unresponsive hai aur requests fail ho rahi hain",
        "container_name": CONTAINER_NAME,
        "system_status": {},
        "similar_incidents": [],
        "diagnosis": "",
        "severity": "",
        "solution": "",
        "approved": False,
        "execution_success": False,
        "execution_result": {},
        "retry_count": 0,
        "incident_id": None,
    }

    print("=" * 60)
    print("Running Day 6 FULL Graph (RAG + MCP + executor + retry loop)...")
    print("=" * 60)

    final_state = compiled_graph.invoke(initial_state)

    print("\nFINAL STATE:")
    for key, value in final_state.items():
        if key == "system_status":
            value = {k: (str(v)[:80] + "...") if k == "recent_logs" else v for k, v in value.items()}
        print(f"  {key}: {value}")

    print("\nNode timings logs/agent.log me dekhein.")


if __name__ == "__main__":
    main()
