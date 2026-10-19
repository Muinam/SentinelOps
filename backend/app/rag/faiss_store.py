# faiss_store.py
#
# Is file ka kaam: FAISS index ko manage karna - vectors ADD karna, SEARCH karna,
# aur ab (Day 6) DISK pe SAVE/LOAD karna taake memory restart ke baad bhi rahe.

import os                                      # os - file/folder paths aur existence check ke liye
import json                                    # json - original texts ko file me save/load karne ke liye
import faiss                                   # FAISS library - vector search engine
import numpy as np                              # numpy - vectors arrays ke liye
from app.rag.embeddings import get_embedding, EMBEDDING_DIM  # Real embedding function (Day 6 ka)


class FaissStore:
    """
    FAISS index ke around ek clean wrapper.
    "incident add karo", "similar incidents dhoondo", "disk pe save/load karo" -
    ye sab simple methods hain, FAISS ki low-level details har jagah nahi likhni padti.
    """

    def __init__(self):
        # IndexFlatL2 - exact (brute-force) search, L2 (Euclidean) distance se
        self.index = faiss.IndexFlatL2(EMBEDDING_DIM)
        # FAISS sirf vectors rakhta hai, ASLI TEXT nahi - isliye texts alag list me
        self.texts = []

    def add_incident(self, incident_text: str) -> None:
        """Ek naya incident text embed karke index me add karta hai."""
        vector = get_embedding(incident_text)                # Text -> vector (real model se)
        vector_2d = np.array([vector], dtype="float32")        # FAISS ko 2D array chahiye: shape (1, 384)
        self.index.add(vector_2d)                               # Index me add karo
        self.texts.append(incident_text)                         # Original text bhi save rakho

    def search(self, query_text: str, top_k: int = 3):
        """Query se sab se SIMILAR incidents dhoondta hai (distance kam = zyada similar)."""
        if self.index.ntotal == 0:                              # Agar index khali hai
            return []                                             # to khali result

        query_vector = get_embedding(query_text)                 # Query ko vector banao
        query_2d = np.array([query_vector], dtype="float32")      # 2D shape
        distances, indices = self.index.search(query_2d, top_k)    # FAISS search

        results = []
        for rank, idx in enumerate(indices[0]):                   # indices[0] - pehli (aur wahid) query ke results
            if idx == -1:                                           # -1 = match nahi mila (data kam hai)
                continue
            results.append({"text": self.texts[idx], "distance": float(distances[0][rank])})
        return results

    # ------------------------------------------------------------------
    # Day 6 NAYA: Persistence (disk pe save / load)
    # ------------------------------------------------------------------
    def save(self, index_path: str) -> None:
        """
        Index + texts dono ko disk pe save karta hai.
        Do files banti hain: <index_path> (FAISS vectors) aur <index_path>.json (texts).
        """
        folder = os.path.dirname(index_path)                      # Folder ka path nikalo (e.g. ./data)
        if folder:                                                  # Agar path me folder hai
            os.makedirs(folder, exist_ok=True)                       # Folder nahi hai to bana do

        faiss.write_index(self.index, index_path)                   # FAISS ka apna save function
        with open(index_path + ".json", "w", encoding="utf-8") as f:  # Texts alag JSON file me
            json.dump(self.texts, f, ensure_ascii=False)               # ensure_ascii=False - Urdu/Hindi chars safe rahein

    def load(self, index_path: str) -> bool:
        """
        Disk se index + texts wapas load karta hai.
        Return: True agar load ho gaya, False agar files nahi mili ya mismatch tha.
        """
        texts_path = index_path + ".json"                           # Texts wali file ka path
        if not (os.path.exists(index_path) and os.path.exists(texts_path)):
            return False                                              # Files hain hi nahi - fresh start

        loaded_index = faiss.read_index(index_path)                  # FAISS index disk se padho
        if loaded_index.d != EMBEDDING_DIM:                           # Dimension match check (model badla ho to)
            return False                                                # Purana/incompatible index - ignore karo

        with open(texts_path, "r", encoding="utf-8") as f:
            loaded_texts = json.load(f)                                # Texts padho

        if len(loaded_texts) != loaded_index.ntotal:                  # Vectors aur texts ki ginti same honi chahiye
            return False                                                # Corrupt/out-of-sync files - ignore karo

        self.index = loaded_index                                     # Sab theek hai - apne index ko replace karo
        self.texts = loaded_texts
        return True
