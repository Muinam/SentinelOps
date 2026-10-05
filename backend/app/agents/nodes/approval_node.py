from app.agents.state import AgentState

def approval_node(state: AgentState) -> AgentState:
    """
    Diagnosis + solution insaan ko dikhata hai, aur HAAN/NA poochta hai.
    """
    print("[NODE] approval_node running...")

    # ---- Insaan ko poori information dikhao decide karne ke liye ----
    print("\n" + "-" * 50)
    print("HUMAN APPROVAL REQUIRED")
    print("-" * 50)
    print(f"Diagnosis : {state.get('diagnosis', 'N/A')}")
    print(f"Severity  : {state.get('severity', 'N/A')}")
    print(f"Solution  : {state.get('solution', 'N/A')}")
    print("-" * 50)

    # Terminal se input lo - ye line yahin RUK jaati hai jab tak insaan type na kare
    answer = input('Is fix ko approve karte hain? (yes/no): ').lower().strip()

    approved = answer in ('yes', 'y', 'haan')

    if approved:
        print("✅ Approved - executor ko bhejte hain...")
    else:
        print("❌ Rejected - fix apply nahi hoga...")

    return {"approved": approved}