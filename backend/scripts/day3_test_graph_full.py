import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.agents.graph import compiled_graph           # Ab 4-node wala graph (shaam ko update hua)
from app.tools.rag_tool import seed_incident_history    # Day 2 RAG seed


def main():
    seed_incident_history(
        [
            "payment-service ne restart loop shuru kar diya OOM ki wajah se, fix: memory limit badhaya",
            "database connection timeout aa raha tha, fix: connection pool size increase kiya",
        ]
    )

    # IMPORTANT: saare AgentState fields ko default values ke sath initialize karo
    # Sirf "error_message" dena risky hai - agar koi node partial fail ho to
    # next node ko woh field "missing" mil sakti hai. Defaults is se bachate hain.
    initial_state = {
        "error_message": "payment-service container baar baar crash ho raha hai",
        "system_status": {},        # monitor_node isko fill karega
        "similar_incidents": [],     # diagnosis_node isko fill karega
        "diagnosis": "",              # diagnosis_node isko fill karega
        "severity": "",                # diagnosis_node isko fill karega
        "solution": "",                 # solution_node isko fill karega
        "incident_id": None,             # reporter_node isko fill karega
    }

    print("=" * 60)
    print("Running Day 3 FULL Graph (4 nodes)...")
    print("=" * 60)

    final_state = compiled_graph.invoke(initial_state)    # Poora flow ek call me chalega

    print("\nFINAL STATE:")
    for key, value in final_state.items():
        print(f"  {key}: {value}")

    print(f"\n✅ Incident saved to Postgres with ID: {final_state.get('incident_id')}")


if __name__ == "__main__":
    main()