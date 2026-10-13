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
}


def track(node_func, before=None, after=None):
    """
    node_func ko wrap karta hai.
      before - node chalne se pehle ye status set karo (None = kuch nahi)
      after  - node ke baad ye status set karo (None = kuch nahi)
    Node ke return me jo SYNC_FIELDS aayein, wo hamesha database me likhe jaate hain.
    """

    @wraps(node_func)                                        # Naam/annotations preserve
    def wrapper(state):
        incident_id = state.get("incident_id")                 # Is run ka incident
        if before:                                              # Pehle wala status
            set_status(incident_id, before)

        update = node_func(state)                                # ASAL node chalao

        incident_id = update.get("incident_id", incident_id)     # Node ne khud ID di ho (intake) to wo
        fields = {                                                # Node ke diye hue sync hone wale fields
            column: update[key]
            for key, column in SYNC_FIELDS.items()
            if key in update and update[key] not in (None, "")    # Khali values nahi likhte
        }
        if after or fields:                                       # Kuch likhna hai
            note = update.get("review_reason") if after else None  # Status ke sath wajah ka note
            set_status(incident_id, after, note, **fields)
        return update                                              # Node ka nateeja bina badle aage

    return wrapper
