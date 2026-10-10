import os                                       # os - logs folder banane ke liye
import time                                      # time - node ka execution time napne ke liye
import logging                                    # Python ka built-in logging module
from functools import wraps                       # wraps - wrapper function asal function ki "identity" bachaye

_LOG_DIR = "logs"                                  # Logs ka folder (backend/logs/)
_LOG_FILE = os.path.join(_LOG_DIR, "agent.log")     # Log file ka path

os.makedirs(_LOG_DIR, exist_ok=True)                 # Folder nahi hai to bana do

_logger = logging.getLogger("sentinelops")            # Ek named logger
_logger.setLevel(logging.INFO)                         # INFO aur us se upar ke messages record hon

if not _logger.handlers:                               # Handlers dobara add na hon (duplicate lines se bachne ke liye)
    fmt = logging.Formatter("%(asctime)s | %(message)s")      # Har line: time | message
    file_handler = logging.FileHandler(_LOG_FILE, encoding="utf-8")  # File me likhne wala
    file_handler.setFormatter(fmt)
    _logger.addHandler(file_handler)


def log_node(node_name: str, node_func):
    """
    Kisi bhi node function ko "wrap" karta hai: chalne se pehle/baad time napta hai aur log likhta hai.
    Node ka apna code BILKUL change nahi hota - ye bahar se lipta hai (decorator pattern).

    Usage (graph.py me): graph.add_node("monitor_step", log_node("monitor", monitor_node))
    """

    @wraps(node_func)                                    # Original function ka naam/annotations preserve karo
    def wrapper(state):
        start = time.time()                                # Shuru ka waqt
        try:
            update = node_func(state)                       # ASAL node chalao
            elapsed = time.time() - start                    # Kitna time laga
            keys = list(update.keys()) if isinstance(update, dict) else []
            _logger.info(f"NODE={node_name} | OK | {elapsed:.2f}s | updated={keys}")
            return update                                     # Result bina badle aage bhejo
        except Exception as e:
            elapsed = time.time() - start
            _logger.info(f"NODE={node_name} | FAILED | {elapsed:.2f}s | error={e}")
            raise                                              # Error ko dobara uthao - chhupana nahi hai

    return wrapper