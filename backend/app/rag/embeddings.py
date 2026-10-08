import numpy as np  # numpy - FAISS ko arrays numpy format me hi chahiye hote hain
from sentence_transformers import SentenceTransformer
EMBEDDING_DIM = 384  # Har vector ki length - jitna bara utna zyada "detail" (yahan demo ke liye chhota rakha)
MODEL_NAME = "all-MiniLM-L6-v2" # fast and light model

_model = None    # Model ek dafa load hoga, phir reuse (loading slow hoti hai)

def _get_model():
    """
    Model ko LAZILY load karta hai - yani sirf tab jab pehli dafa zaroorat pade.
    Isse jin scripts ko embeddings nahi chahiye, unka startup tez rehta hai.
    """
    global _model

    if _model is None:
        _model = SentenceTransformer(MODEL_NAME)

    return _model


def get_embedding(text:str) -> np.ndarray:
    """
    Text ko ek 384-numbers ke vector me convert karta hai - REAL meaning ke sath.
    Similar meaning wale texts ke vectors ek dusre ke "qareeb" hote hain.
    """
    model = _get_model()

    # normalize_embeddings=True - vector ki length 1 kar deta hai, jisse
    # similarity comparison fair rehta hai (cosine similarity jaisa behave karta hai)
    vector = model.encode([text], convert_to_numpy=True)
    
    return np.asarray(vector, dtype="float32").reshape(-1)
