from app.agents.state import AgentState

def approval_node(state: AgentState) -> AgentState:
    """
    Diagnosis + solution insaan ko dikhata hai, aur HAAN/NA poochta hai.
    """
    print("[NODE] approval_node running...")

    # ---- Insaan ko poori information dikhao decide karne ke liye ----
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

    # Terminal se input lo - ye line yahin RUK jaati hai jab tak insaan type na kare
    answer = input('Is fix ko approve karte hain? (yes/no): ').lower().strip()

    approved = answer in ('yes', 'y', 'haan')

    if approved:
        print("✅ Approved - executor ko bhejte hain...")
    else:
        print("❌ Rejected - fix apply nahi hoga...")

    return {"approved": approved}