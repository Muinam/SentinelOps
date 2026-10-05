import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.tools.docker_tool import check_container_status, read_container_logs, _get_client


def main():
    # ---- STEP 1: Pehle sab running containers LIST karo ----
    # Taake pata chale aapke system pe konse containers chal rahe hain test karne ke liye
    print("Listing all running containers...")
    try:
        client = _get_client()
        containers = client.containers.list()          # Sab RUNNING containers (all=True dalo agar stopped bhi chahiye)

        if not containers:
            print("  Koi container nahi chal raha. Pehle 'docker run' se ek container start karein.")
            print("  Example: docker run -d --name test-nginx nginx")
            return

        for c in containers:
            print(f"  - {c.name} (status: {c.status})")

        # ---- STEP 2: Pehle container ka naam uthao test ke liye ----
        test_container = containers[0].name

    except Exception as e:
        print(f"Docker se connect nahi ho saka: {e}")
        print("Confirm karein Docker Desktop chal raha hai.")
        return

    # ---- STEP 3: Us container ka status check karo (hamara tool function) ----
    print(f"\nChecking status of '{test_container}'...")
    status = check_container_status(test_container)
    print(f"  {status}")

    # ---- STEP 4: Us container ke logs padho (hamara tool function) ----
    print(f"\nReading last 10 logs of '{test_container}'...")
    logs = read_container_logs(test_container, tail=10)
    print(f"  {logs.get('logs', logs.get('error'))}")


if __name__ == "__main__":
    main()
