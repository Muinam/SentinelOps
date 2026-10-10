# debug_rag.py
#
# Maqsad: "similar_incidents khali kyun aa rahi hai" ka sabab dhoondna.
# Ye script RAG pipeline ke har layer ko ALAG test karti hai, taake pata chale
# pehli gadbad KAHAN hai (aur kaunsi file theek karni hai).
#
# Run karne ka tareeqa (backend folder se, venv activate ho):
#   python -m scripts.debug_rag

import sys                                          # sys - import path badalne ke liye
import os                                           # os - file paths banane ke liye
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))  # "app" folder import ke liye add karo

import numpy as np                                  # numpy - vector ka shape/NaN check karne ke liye
from app.tools import rag_tool                      # RAG tool (isme _store aur search function hai)
from app.rag.embeddings import get_embedding, EMBEDDING_DIM  # Embedding function aur uski expected length

QUERY = "test-nginx container unresponsive hai aur requests fail ho rahi hain"  # Wahi query jo graph me use hoti hai

print("=" * 60)                                      # Sirf readability ke liye separator
print("RAG DEBUG - har layer alag check ho rahi hai")
print("=" * 60)

# ---------------------------------------------------------------
# STEP 1: Memory me kitne incidents hain? (rag_tool.py / faiss_store.py load)
# ---------------------------------------------------------------
store = rag_tool._store                              # rag_tool ka shared FaissStore object
print("\n[STEP 1] Memory check")
print(f"  index.ntotal (vectors) : {store.index.ntotal}")   # FAISS me kitne vectors hain
print(f"  len(texts)             : {len(store.texts)}")      # Original texts ki ginti
print(f"  index dimension        : {store.index.d} (expected {EMBEDDING_DIM})")  # Vector ki length match honi chahiye
for i, t in enumerate(store.texts):                  # Har saved text ki chhoti jhalak
    print(f"    #{i}: {t[:70]}")                     # Sirf pehle 70 characters
if store.index.ntotal == 0:                          # Agar memory khali hai
    print("  >>> PROBLEM: memory khali hai -> faiss_store.py load() ya rag_tool.py check karein")
if store.index.ntotal != len(store.texts):           # Vectors aur texts ki ginti alag ho to gadbad hai
    print("  >>> PROBLEM: vectors aur texts ki ginti alag hai -> faiss_store.py save/load")

# ---------------------------------------------------------------
# STEP 2: Embedding sahi ban rahi hai? (embeddings.py)
# ---------------------------------------------------------------
print("\n[STEP 2] Embedding check")
vec = get_embedding(QUERY)                           # Query ka vector banao (pehli dafa model load hoga)
print(f"  shape : {vec.shape} (expected ({EMBEDDING_DIM},))")  # 1D aur 384 length honi chahiye
print(f"  dtype : {vec.dtype}")                       # float32 hona chahiye
print(f"  NaN?  : {bool(np.isnan(vec).any())}")       # NaN values FAISS ko -1 results dene par majboor karti hain
print(f"  norm  : {float(np.linalg.norm(vec)):.3f} (normalized ho to ~1.0)")  # Vector ki lambai
if vec.shape != (EMBEDDING_DIM,) or np.isnan(vec).any():  # Shape galat ya NaN mila
    print("  >>> PROBLEM: embedding galat hai -> embeddings.py")

# ---------------------------------------------------------------
# STEP 3: FAISS ka KACHA search (wrapper ke bina) - -1 ka matlab "match nahi mila"
# ---------------------------------------------------------------
print("\n[STEP 3] Raw FAISS search")
query_2d = np.asarray(vec, dtype="float32").reshape(1, -1)   # FAISS ko (1, 384) shape chahiye
distances, indices = store.index.search(query_2d, 3)          # Seedha FAISS se top 3 maango
print(f"  indices   : {indices[0].tolist()}")           # -1 dikhe to matlab match nahi mila
print(f"  distances : {[round(float(d), 3) for d in distances[0]]}")  # Distance jitni kam, match utna behtar
if store.index.ntotal > 0 and all(i == -1 for i in indices[0]):  # Data hai lekin sab -1
    print("  >>> PROBLEM: FAISS koi match nahi de raha -> embeddings.py ya saved index corrupt")

# ---------------------------------------------------------------
# STEP 4: Hamara wrapper function (graph yehi call karta hai)
# ---------------------------------------------------------------
print("\n[STEP 4] rag_tool.search_similar_incidents()")
result = rag_tool.search_similar_incidents(QUERY)             # Wahi function jo diagnosis_node use karta hai
found = result.get("similar_incidents", [])                    # Results ki list (khali ho sakti hai)
print(f"  results mile : {len(found)}")                        # Kitne incidents wapas aaye
for item in found:                                              # Har result ka text aur distance
    print(f"    - {item['text'][:60]}  (distance {item['distance']:.3f})")
if not found and store.index.ntotal > 0:                       # Memory me data hai magar result khali
    print("  >>> PROBLEM: faiss_store.py ka search() ya rag_tool.py")

# ---------------------------------------------------------------
# STEP 5: diagnosis_node.py aakhir me "similar_incidents" state me daalta hai ya nahi?
# ---------------------------------------------------------------
print("\n[STEP 5] diagnosis_node.py me 'similar_incidents' wali lines")
node_path = os.path.join(os.path.dirname(__file__), "..", "app", "agents", "nodes", "diagnosis_node.py")  # File ka path
with open(node_path, "r", encoding="utf-8") as f:               # File padho
    lines = f.read().splitlines()                                 # Line by line list
hits = [(n + 1, ln.strip()) for n, ln in enumerate(lines) if "similar_incidents" in ln]  # Matching lines
for number, text in hits:                                         # Line number ke sath print karo
    print(f"    line {number}: {text}")
if not any(ln.startswith('"similar_incidents"') or "'similar_incidents'" in ln or '"similar_incidents":' in ln
           for _, ln in hits):                                    # Return dict me key hi na ho
    print("  >>> PROBLEM: diagnosis_node.py ke return me 'similar_incidents' key nahi mili")

print("\nDebug khatam. Upar jahan '>>> PROBLEM' likha hai, wahi file theek karni hai.")