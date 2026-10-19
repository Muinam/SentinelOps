# lifecycle.py
#
# Is file ka kaam: kisi bhi node ko "lifecycle wrapper" me lapetna (log_node ki tarah).
# Node chalne se PEHLE ek status set kar sakta hai (jaise "awaiting_approval"), aur node ke
# BAAD uske diye hue fields (diagnosis, severity...) database me sync karta hai.
# Faida: nodes ka apna code database se saaf rehta hai, aur graph.py me ek nazar me dikh jata
# hai ke kaunsa node kaunsa status set karta hai.

import json                                                # json - evidence list ko text me badalne ke liye
from functools import wraps                                # wraps - wrapper asal function ki pehchaan bachaye
from app.db.incidents import set_status                    # Best-effort database update

# State ke kaunse fields database ke kaunse columns me jaate hain
SYNC_FIELDS = {
    "diagnosis": "diagnosis",
    "severity": "severity",
    "confidence": "confidence",
    "solution": "solution",
    "recommended_action": "recommended_action",
    "retry_count": "retry_count",
    "review_reason": "review_reason",
    "diagnosis_evidence": "evidence",                           # Day 9-11: evidence quotes (JSON text ban kar)
    "approval_decision": "approval_decision",                    # Auto-policy ke faisle ke liye
    "approved_by": "approved_by",
    "approval_note": "approval_note",
}


def track(node_func, before=None, after=None):
    """
    node_func ko wrap karta hai.
      before - node chalne se pehle ye status set karo (None = kuch nahi)
      after  - node ke baad ye status set karo (None = kuch nahi)
    Node ke return me jo SYNC_FIELDS aayein, wo hamesha database me likhe jaate hain.
    after ek function bhi ho sakta hai: after(update) -> status ya None (jaise policy node: "human" ho to awaiting_approval).
    """

    @wraps(node_func)                                        # Naam/annotations preserve
    def wrapper(state):
        incident_id = state.get("incident_id")                 # Is run ka incident
        if before:                                              # Pehle wala status
            set_status(incident_id, before)

        update = node_func(state)                                # ASAL node chalao

        incident_id = update.get("incident_id", incident_id)     # Node ne khud ID di ho (intake) to wo
        fields = {                                                # Node ke diye hue sync hone wale fields
            column: (json.dumps(update[key], ensure_ascii=False) if key == "diagnosis_evidence" else update[key])
            for key, column in SYNC_FIELDS.items()
            if key in update and update[key] not in (None, "", [])   # Khali values nahi likhte
        }
        status_after = after(update) if callable(after) else after   # after function ho to usse poocho
        if status_after or fields:                                  # Kuch likhna hai
            note = update.get("review_reason") if status_after else None   # Status ke sath wajah ka note
            set_status(incident_id, status_after, note, **fields)
        return update                                              # Node ka nateeja bina badle aage

    return wrapper
