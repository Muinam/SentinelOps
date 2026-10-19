# checkpointing.py
#
# Is file ka kaam: graph ki PAUSE hui state ko save karne wala "checkpointer" dena.
# Jab graph approval se pehle rukta hai, uski poori state yahan save hoti hai - process band ho jaye
# ya worker restart ho, tab bhi graph wahin se resume ho sakta hai.
#   "sqlite" - ek local file (default; single worker ke liye kaafi, Docker volume me bhi chalti hai)
#   "memory" - sirf RAM me (tests ke liye; process band to sab gayab)
# NOTE: LangGraph ka Postgres checkpointer bhi hota hai, lekin wo alag driver (psycopg v3) maangta hai
# aur Supabase ke connection pooler ke sath alag settings chahiye - isliye abhi SQLite.

import os                                                    # os - folder banane ke liye
import sqlite3                                                # sqlite3 - Python ka built-in SQLite
from langgraph.checkpoint.memory import MemorySaver           # RAM wala checkpointer
from app.config import get_settings                           # .env ki settings


def get_checkpointer(kind: str = "sqlite", path: str = None):
    """Checkpointer banata hai. kind: "sqlite" ya "memory". path - sqlite file (None = settings ka checkpoint_path)."""
    if kind == "memory":
        return MemorySaver()                                   # RAM me - restart par gayab

    from langgraph.checkpoint.sqlite import SqliteSaver        # Yahin import - memory mode me ye package na ho to bhi chale
    file_path = path or get_settings().checkpoint_path          # Kahan save karni hai
    folder = os.path.dirname(file_path)                          # Folder ka path
    if folder:
        os.makedirs(folder, exist_ok=True)                        # Folder nahi hai to bana do
    connection = sqlite3.connect(file_path, check_same_thread=False)   # File se connection (threads ke beech safe)
    return SqliteSaver(connection)                                 # Checkpointer
