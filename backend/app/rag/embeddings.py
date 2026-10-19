# embeddings.py
#
# Is file ka kaam: text ko NUMBERS ki list (vector) me convert karna - lekin ab
# REAL semantic model se (Day 1 ka fake hashing wala version replace ho gaya).
#
# Model: "all-MiniLM-L6-v2" - open-source, free, chhota (~80MB), local chalta hai,
# koi API key/paid service nahi chahiye. Pehli dafa chalane par internet se
# download hota hai, uske baad local cache se load hota hai.

import numpy as np                                    # numpy - FAISS ko arrays numpy format me chahiye

EMBEDDING_DIM = 384                                    # all-MiniLM-L6-v2 har text ka 384 numbers ka vector banata hai
MODEL_NAME = "all-MiniLM-L6-v2"                         # HuggingFace model ka naam

_model = None                                           # Model ek dafa load hoga, phir reuse (loading slow hoti hai)


def _get_model():
    """
    Model ko LAZILY load karta hai - yani sirf tab jab pehli dafa zaroorat pade.
    Isse jin scripts ko embeddings nahi chahiye, unka startup tez rehta hai.
    """
    global _model                                        # Module-level variable update karne ke liye
    if _model is None:                                    # Agar abhi tak load nahi hua
        # Import yahin andar kiya - sentence_transformers bhaari library hai,
        # isko file ke top pe import karte to har import par slow hota
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(MODEL_NAME)           # Model download/load karo
    return _model                                          # Loaded model return karo


def get_embedding(text: str) -> np.ndarray:
    """
    Text ko ek 384-numbers ke vector me convert karta hai - REAL meaning ke sath.
    Similar meaning wale texts ke vectors ek dusre ke "qareeb" hote hain.
    """
    model = _get_model()                                    # Model lo (pehli dafa load hoga)

    # normalize_embeddings=True - vector ki length 1 kar deta hai, jisse
    # similarity comparison fair rehta hai (cosine similarity jaisa behave karta hai)
    vector = model.encode(text, normalize_embeddings=True)

    return vector.astype("float32")                         # FAISS ko float32 chahiye hota hai
