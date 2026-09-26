# day1_test_faiss.py
#
# DAY 1 - EVENING TASK
# Goal: FAISS ka mechanism samajhna - standalone, koi LLM involved nahi abhi
# (LLM ke sath integration Day 2 me hogi)
#
# Run karne ka tareeqa:
#   cd backend
#   python -m scripts.day1_test_faiss

import sys                                        # sys - path handling
import os                                         # os - file path utilities
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # "app" folder import ke liye add karo

from app.rag.faiss_store import FaissStore         # Hamara FAISS wrapper class


# ---- STEP 1: Kuch dummy purane incidents (jaise real system me DB se aate) ----
dummy_incidents = [
    "payment-service container crash ho gaya CPU spike ki wajah se",
    "database connection timeout errors bar bar aa rahe hain",
    "auth-service 502 bad gateway de raha hai high traffic ke waqt",
    "redis cache memory full ho gayi, eviction errors aa rahe hain",
    "payment-service ne restart loop shuru kar diya OOM (out of memory) ki wajah se",
]


def main():
    # ---- STEP 2: FaissStore object banao ----
    store = FaissStore()                            # Naya, khali FAISS index

    # ---- STEP 3: Saare dummy incidents index me add karo ----
    print("Adding incidents to FAISS index...")
    for incident in dummy_incidents:                 # Har incident ke liye loop
        store.add_incident(incident)                  # Index me add karo
        print(f"  Added: {incident}")

    print(f"\nTotal incidents in index: {store.index.ntotal}")  # Kitne vectors store hue, confirm karo

    # ---- STEP 4: Ek NAYA query karo jo purane incidents se milta julta ho ----
    query = "payment service baar baar restart ho raha hai, memory issue lag raha hai"

    print(f"\nSearching for incidents similar to:\n  '{query}'\n")

    # ---- STEP 5: Search chalao aur top 3 similar incidents dhoondo ----
    results = store.search(query, top_k=3)

    # ---- STEP 6: Results print karo ----
    print("Top matches:")
    for rank, result in enumerate(results, start=1):    # start=1 taake numbering 1 se shuru ho
        print(f"  {rank}. {result['text']}  (distance: {result['distance']:.4f})")
        # Note: distance jitni KAM ho, match utna hi BEHTAR/similar hota hai


if __name__ == "__main__":
    main()                                                # Script run hone par main() call karo
