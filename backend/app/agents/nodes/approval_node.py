from app.agents.state import AgentState

def approval_node(state: AgentState) -> AgentState:
    """Insaan ko poori information dikhata hai aur HAAN/NA poochta hai."""
    print("[NODE] approval_node running...")

    print("\n" + "-" * 60)
    print("HUMAN APPROVAL REQUIRED")
    print("-" * 60)
    print(f"Root cause : {state.get('diagnosis', 'N/A')}")
    print(f"Severity   : {state.get('severity', 'N/A')}   Confidence: {state.get('confidence', 'N/A')}")
    print("Evidence   :")
    for quote in state.get("diagnosis_evidence", []):                # Har evidence quote alag line me
        print(f"   - {quote}")
    print(f"Critic     : diagnosis supported = {state.get('critic_supported')}")
    print(f"Action     : {state.get('recommended_action', 'N/A')}  (yehi ACTION chalega, aur kuch nahi)")
    print(f"Why        : {state.get('solution', 'N/A')}")
    print("-" * 60)

    answer = input("Is action ko approve karte hain? (yes/no): ").strip().lower()   # Yahin ruk jata hai
    approved = answer in ("yes", "y", "haan")                          # Flexible matching

    if approved:
        print("✅ Approved - executor ko bhejte hain...")
        return {"approved": True}
    print("❌ Rejected - action nahi hoga...")
    return {"approved": False, "review_reason": "A human rejected the proposed action."}


def external_approval_node(state: AgentState) -> AgentState:
    """
    WORKER MODE ka approval node. Graph approval se PEHLE ruk jata hai (interrupt_before), phir
    worker DB ka faisla (approve.py se likha hua) state me bhar kar graph resume karta hai.
    Ye node input() NAHI poochta - sirf wo faisla lagata hai jo state me aa chuka hai.
    """
    print("[NODE] approval_node (external faisla) running...")

    if not state.get("approval_decided"):                               # Kisi ne faisla nahi kiya (nahi hona chahiye)
        print("❌ Koi faisla record nahi hua - safe side par reject")
        return {"approved": False, "review_reason": "No approval decision was recorded; failing safe."}

    who = state.get("approved_by") or "unknown"                           # Kis ne faisla kiya
    note = state.get("approval_note") or ""                                # Faisle ka note
    if state.get("approved"):
        print(f"✅ Approved by {who} - executor ko bhejte hain...")
        return {"approved": True}
    print(f"❌ Rejected by {who}")
    return {"approved": False, "review_reason": f"Rejected by {who}" + (f": {note}" if note else "")}
