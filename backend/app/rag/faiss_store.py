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
        # IndexFlatL2 - sab se simple FAISS index type
        # "Flat" ka matlab: har search me SAARE vectors se distance calculate hoti hai (exact search)
        # "L2" ka matlab: Euclidean distance use hoti hai similarity measure karne ke liye
        self.index = faiss.IndexFlatL2(EMBEDDING_DIM)

        # FAISS sirf vectors store karta hai, ASLI TEXT nahi
        # Isliye hum apni side par ek list rakhte hain jo index-position -> original text map kare
        self.texts = []

    def add_incident(self, incident_text: str) -> None:
        """
        Ek naya incident text FAISS index me add karta hai.
        """
        vector = get_embedding(incident_text)             # Text ko vector me convert karo

        # FAISS ko 2D array chahiye hota hai (batch of vectors), isliye reshape karte hain
        vector_2d = np.array([vector], dtype="float32")    # Shape: (1, EMBEDDING_DIM)

        self.index.add(vector_2d)                          # Vector ko FAISS index me add karo
        self.texts.append(incident_text)                   # Original text ko humari list me bhi save karo

    def search(self, query_text: str, top_k: int = 3):
        """
        Query text se sab se zyada SIMILAR incidents dhoondta hai.
        top_k = kitne results chahiye (default 3)
        """
        if self.index.ntotal == 0:                          # Agar index khali hai
            return []                                         # to khali result return karo

        query_vector = get_embedding(query_text)             # Query ko bhi vector me convert karo
        query_2d = np.array([query_vector], dtype="float32")  # FAISS ke liye 2D shape

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
