import os
import json
import faiss                                  # FAISS library - vector search engine
import numpy as np                             # numpy - vectors arrays ke liye
from app.rag.embeddings import get_embedding, EMBEDDING_DIM  # Hamara embedding function


class FaissStore:
    """
    Ye class FAISS index ke around ek clean wrapper hai.
    Isse hum "incidents add karo" aur "similar incidents dhoondo" jaise simple methods use kar sakte hain,
    bina FAISS ki low-level details har jagah likhe.
    """

    def __init__(self):
         # IndexFlatL2 - exact (brute-force) search, L2 (Euclidean) distance se
        self.index = faiss.IndexFlatL2(EMBEDDING_DIM)
        # FAISS sirf vectors rakhta hai, ASLI TEXT nahi - isliye texts alag list me
        self.texts = []

    def add_incident(self, incident_text: str) -> None:
        """Ek naya incident text embed karke index me add karta hai."""
        vector = get_embedding(incident_text)                # Text -> vector (real model se)
        vector_2d = np.asarray(vector, dtype="float32").reshape(1, -1)
        if vector_2d.shape[1] != EMBEDDING_DIM:                 # Safety check - length galat ho to saaf error
            raise ValueError(
                f"Embedding ki length {vector_2d.shape[1]} hai, lekin {EMBEDDING_DIM} chahiye. "
                f"embeddings.py ka model/EMBEDDING_DIM check karein."
            )
        self.index.add(vector_2d)                               # Index me add karo
        self.texts.append(incident_text)                        # Original text bhi save rakho

    def search(self, query_text: str, top_k: int = 3):
        """
        Query text se sab se zyada SIMILAR incidents dhoondta hai.
        top_k = kitne results chahiye (default 3)
        """
        if self.index.ntotal == 0:                          # Agar index khali hai
            return []                                         # to khali result return karo

        query_vector = get_embedding(query_text)             # Query ko bhi vector me convert karo
        query_2d = np.asarray(query_vector, dtype="float32").reshape(1, -1)

        # index.search() do cheezein return karta hai:
        # distances - kitni "door" hai match (kam = zyada similar)
        # indices - kaunse position par match mila
        distances, indices = self.index.search(query_2d, top_k)

        results = []                                           # Final results yahan collect karenge
        for rank, idx in enumerate(indices[0]):                # indices[0] kyunki humne sirf 1 query bheji thi
            if idx == -1:                                       # -1 ka matlab match nahi mila (kam data)
                continue                                         # Isko skip karo
            results.append(
                {
                    "text": self.texts[idx],                    # Original incident text
                    "distance": float(distances[0][rank]),       # Kitna similar hai (kam = behtar)
                }
            )

        return results                                           # List of matching incidents return karo


# NAYA: Persistence (disk pe save / load)

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
