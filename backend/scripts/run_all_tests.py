# run_all_tests.py
#
# Maqsad: saari offline test suites ek command se chalana aur ek jaisa summary dikhana.
#   python -m scripts.run_all_tests

import os                                                          # os - paths ke liye
import re                                                          # re - "ALL 31 ... PASSED" line dhoondne ke liye
import sys                                                         # sys - python ka path aur exit code
import subprocess                                                  # subprocess - har suite alag process me

BACKEND = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))   # backend folder

# (naam, module) - har suite alag process me chalti hai, taake ek doosre ko na chhedein
SUITES = [
    ("Agent (structured output, ReAct, critic, lifecycle)", "tests.test_hardening"),
    ("Automation (policy, watcher, worker, approval)", "tests.test_automation"),
    ("API (FastAPI + worker end-to-end)", "tests.test_api"),
    ("LLM router (retry, fallback)", "tests.test_llm_router"),
]


def main() -> int:
    failed = []                                                      # Jo suites fail hui
    print("=" * 64)
    for title, module in SUITES:
        result = subprocess.run([sys.executable, "-m", module], cwd=BACKEND, capture_output=True, text=True)   # Suite chalao
        combined = result.stdout + result.stderr                      # Poora output
        summary = re.findall(r"^ALL \d+ .*PASSED$", result.stdout, flags=re.MULTILINE)   # "ALL 31 CHECKS PASSED"
        if result.returncode == 0 and summary:
            print(f"✅ {title}\n   {summary[-1]}")
        else:
            print(f"❌ {title}")
            failed.append(module)
            print("   --- aakhri output ---")
            for line in combined.strip().splitlines()[-14:]:           # Aakhri 14 lines
                print("   " + line)
    print("=" * 64)
    if failed:
        print(f"FAIL: {len(failed)} suite(s): {', '.join(failed)}")
        print("Error ka aakhri hissa mujhe bhej dein - main bata dunga kaunsi file update karni hai.")
        return 1
    print("Sab suites pass.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
