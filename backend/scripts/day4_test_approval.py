import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.agents.graph import compiled_graph
from app.tools.rag_tool import seed_incident_history


def main():
    seed_incident_history(
        [
            "payment-service ne restart loop shuru kar diya OOM ki wajah se, fix: memory limit badhaya",
            "database connection timeout aa raha tha, fix: connection pool size increase kiya",
        ]
    )

    # Saare fields default values ke sath initialize karo
    initial_state = {
        "error_message": "payment-service container baar baar crash ho raha hai",
        "system_status": {},
        "similar_incidents": [],
        "diagnosis": "",
        "severity": "",
        "solution": "",
        "approved": False,           # Naya field - Day 4
        "incident_id": None,
    }

    print("=" * 60)
    print("Running Day 4 Graph (with Human Approval Gate)...")
    print("=" * 60)

    final_state = compiled_graph.invoke(initial_state)    # Yahan beech me RUKEGA (input() ki wajah se)

    print("\nFINAL STATE:")
    for key, value in final_state.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
