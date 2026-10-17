import os
import sqlite3
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.sqlite import SqliteSaver
from app.config import get_settings

def get_checkpointer(kind:str = "sqlite", path: str= None):
    """Checkpointer banata hai. kind: "sqlite" ya "memory". path - sqlite file (None = settings ka checkpoint_path)."""    
    if kind == "memory":
        return MemorySaver()

    file_path = path or get_settings().checkpoint_path          # Kahan save karni hai
    folder = os.path.dirname(file_path)                          # Folder ka path
    if folder:
        os.makedirs(folder, exist_ok=True)               # Folder nahi hai to bana do
    connection = sqlite3.connect(file_path, check_same_thread=False)   # File se connection (threads ke beech safe)
    return SqliteSaver(connection)
    
