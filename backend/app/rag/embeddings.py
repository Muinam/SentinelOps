import hashlib     # hashlib - text ko deterministic numbers me convert karne ke liye
import numpy as np  # numpy - FAISS ko arrays numpy format me hi chahiye hote hain

EMBEDDING_DIM = 128  # Har vector ki length - jitna bara utna zyada "detail" (yahan demo ke liye chhota rakha)


def get_embedding(text: str) -> np.ndarray:
    """
    Text ko ek fixed-length numeric vector me convert karta hai.

    Kaise kaam karta hai (demo logic):
    1. Text ko lowercase + words me split karte hain
    2. Har word ka hash lete hain aur usse vector ke andar ek position "activate" karte hain
    3. Isse similar words wale texts ke vectors bhi similar ban jaate hain

    Production replacement: yahan par Anthropic/Voyage/OpenAI embedding API call hogi
    """

    vector = np.zeros(EMBEDDING_DIM, dtype="float32")  # Shuru me sab zero ka vector banao

    words = text.lower().split()                        # Text ko chhote alfaaz (words) me todo

    for word in words:                                   # Har word ke liye loop chalao
        # Word ka MD5 hash lo aur usse integer me convert karo
        hash_val = int(hashlib.md5(word.encode()).hexdigest(), 16)

        # Hash ko vector ki length ke andar fit karo (modulo operation)
        index = hash_val % EMBEDDING_DIM

        vector[index] += 1.0                             # Us position ki value badhao (word "present" hai)

    # Vector ko normalize karo (length 1 banao) - isse similarity comparison fair rehta hai
    norm = np.linalg.norm(vector)                        # Vector ki magnitude (length) nikalo
    if norm > 0:                                          # Zero-division se bachne ke liye check
        vector = vector / norm                            # Har value ko norm se divide karo

    return vector                                          # Final numeric vector return karo
