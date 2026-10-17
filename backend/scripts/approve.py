# approve.py
#
# Maqsad: ruke hue incident par insaan ka FAISLA likhna (approve ya reject).
# Ye sirf database me faisla likhta hai - asal kaam (restart waghera) WORKER karta hai
# jab wo agle round me ye faisla dekhta hai. Baad me FastAPI endpoint bhi yahi function use karega.
#
#   python -m scripts.approve 15 yes
#   python -m scripts.approve 15 no --note "pehle logs khud dekhne hain"
#   python -m scripts.approve 15 yes --by inam

import sys                                                          # sys - exit code aur import path
import os                                                           # os - path banane ke liye
import argparse                                                      # argparse - command line options
import getpass                                                        # getpass - computer ke user ka naam
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))      # "app" folder import ke liye add karo

from app.db.database import SessionLocal                             # DB session
from app.db.migrate import ensure_schema                             # Schema up-to-date
from app.db import crud                                               # record_decision


def main() -> int:
    parser = argparse.ArgumentParser(description="Incident par approval ka faisla")
    parser.add_argument("incident_id", type=int, help="incident ka ID (show_incident se dekhein)")
    parser.add_argument("decision", choices=["yes", "no"], help="yes = approve, no = reject")
    parser.add_argument("--by", default=getpass.getuser(), help="faisla kis ne kiya (default: computer ka user)")
    parser.add_argument("--note", default=None, help="chhota note")
    args = parser.parse_args()

    ensure_schema()                                                   # Purani table me naye columns na hon to jod do
    db = SessionLocal()
    try:
        ok, message = crud.record_decision(db, args.incident_id, args.decision == "yes", args.by, args.note)
    finally:
        db.close()

    print(("✅ " if ok else "❌ ") + message)
    if ok:
        print("Worker agle round me is faisle par graph resume karega.")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
