# rag_tool.py
#
# Is file ka kaam: FaissStore ko "LLM tool" ki shakal dena (schema + wrapper),
# aur ab (Day 6) disk persistence ke sath: start par purani memory load hoti hai,
# naya incident aane par turant disk pe save hota hai.

from app.config import get_settings                 # .env se FAISS_INDEX_PATH lene ke liye
from app.rag.faiss_store import FaissStore          # FAISS wrapper

settings = get_settings()

# ---- Ek shared FaissStore (poori app me ek hi) ----
_store = FaissStore()

# ---- Start hote hi disk se purani memory load karne ki koshish ----
_loaded = _store.load(settings.faiss_index_path)     # True = purani memory mil gayi, False = fresh start
if _loaded:
    print(f"[RAG] Disk se {_store.index.ntotal} purane incidents load hue")
else:
    print("[RAG] Koi saved memory nahi mili - khali index se shuru")


def seed_incident_history(incident_texts: list[str]) -> None:
    """
    DEV/TEST helper (Day 2-4 ke scripts isko use karte hain): dummy incidents memory me daalta hai.
    NOTE: ye disk pe save NAHI karta - sirf temporary testing ke liye hai.
    """
    for text in incident_texts:
        _store.add_incident(text)


def remember_incident(text: str) -> None:
    """
    Day 6 NAYA: ek REAL incident ko memory me add karta hai AUR turant disk pe save karta hai.
    Reporter node incident resolve hone ke baad isko call karta hai - yehi "continuous ingestion" hai.
    """
    _store.add_incident(text)                          # Embed + index me add
    _store.save(settings.faiss_index_path)              # Disk pe save - restart ke baad bhi yaad rahe


def memory_size() -> int:
    """Kitne incidents memory me hain - debugging/test ke liye."""
    return _store.index.ntotal


def search_similar_incidents(query: str) -> dict:
    """
    YE WO FUNCTION HAI jo LLM/node call karta hai past similar incidents dekhne ke liye.
    """
    results = _store.search(query, top_k=3)             # Top 3 similar
    if not results:
        return {"message": "No similar past incidents found."}
    return {"similar_incidents": results}


# ---- Tool ka SCHEMA (Groq/OpenAI-style) ----
RAG_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "search_similar_incidents",
        "description": (
            "Search past incident history for similar errors or issues. "
            "Use this BEFORE proposing a fix, to check if this problem "
            "happened before and how it was resolved."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "A short description of the current error/incident"}
            },
            "required": ["query"],
        },
    },
}
