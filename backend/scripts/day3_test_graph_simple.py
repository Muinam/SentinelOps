import sys                                        # sys - path manipulation
import os                                         # os - file paths
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # "app" folder import path me

from app.agents.graph import compiled_graph         # Day 3 subah ka compiled graph
from app.tools.rag_tool import seed_incident_history  # Day 2 ka RAG seed function


def main():
    # ---- STEP 1: FAISS me kuch dummy incidents daal do (RAG ke liye) ----
    seed_incident_history(
        [
            "payment-service ne restart loop shuru kar diya OOM ki wajah se, fix: memory limit badhaya",
            "database connection timeout aa raha tha, fix: connection pool size increase kiya",
        ]
    )

    # ---- STEP 2: Graph ko INVOKE karo - initial state dena hota hai ----
    # Baaki fields (system_status, diagnosis waghera) abhi khali hain - nodes unhe fill karenge
    initial_state = {"error_message": "payment-service container baar baar crash ho raha hai"}

    print("=" * 60)
    print("Running Day 3 Simple Graph (2 nodes)...")
    print("=" * 60)

    final_state = compiled_graph.invoke(initial_state)  # Graph chalao - ye poora flow run karega

    # ---- STEP 3: Final state print karo - dekho kya kya fill hua ----
    print("\nFINAL STATE:")
    for key, value in final_state.items():               # Har field print karo
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
