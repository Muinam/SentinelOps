from app.db.database import settings
from app.rag.faiss_store import FaissStore

_store = FaissStore()              # Underscore = "internal use only" convention


_loaded = _store.load(settings.faiss_index_path)
if _loaded:
    print(f"[RAG] Disk se {_store.index.ntotal} purane incidents load hue")
else:
    print("[RAG] Koi saved memory nahi mili - khali index se shuru")


def seed_incident_history(incident_texts: list[str]) -> None:
    """
    Dummy/starter incidents ko FAISS index me load karta hai.
    Real system me ye Postgres se past incidents utha kar karega (Day 2 shaam ke baad).
    """
    for text in incident_texts:
        _store.add_incident(text)       # FAISS index me add karo


def remember_incident(text:str) -> None:
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
    YE WO FUNCTION HAI jo LLM "call" karega jab usko past similar
    incidents dekhne hon. Naam aur behavior tool schema se match hona chahiye
    """
    results = _store.search(query, top_k=3)

    if not results:
        return {'message': 'No Similar past incident found.'}
    
    return {'similar_incident': results}


# ---- Tool ka SCHEMA (Groq/OpenAI-style format, Day 1 wale format jaisa) ----
RAG_TOOL_SCHEMA = {
    "type": "function",                                  # Groq/OpenAI convention
    "function": {
        "name": "search_similar_incidents",               # Function name se match hona chahiye
        "description": (                                    # LLM isi se samjhega kab use karna hai
            "Search past incident history for similar errors or issues. "
            "Use this BEFORE proposing a fix, to check if this problem "
            "happened before and how it was resolved."
        ),
        "parameters": {                                     # Input schema
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "A short description of the current error/incident",
                }
            },
            "required": ["query"],                          # query dena zaroori hai
        },
    },
}

    