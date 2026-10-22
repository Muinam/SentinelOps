# run_api.py
#
# Maqsad: API ko .env ki settings (host, port) ke sath chalana.
#   python -m scripts.run_api

import sys                                                          # sys - import path
import os                                                           # os - path banane ke liye
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))      # "app" folder import ke liye add karo

import uvicorn                                                       # uvicorn - FastAPI chalane wala server
from app.config import get_settings                                   # .env ki settings


def main():
    settings = get_settings()
    if not settings.api_key:                                          # Key nahi to endpoints 503 denge
        print("⚠️  API_KEY .env me set nahi hai - /incidents ke endpoints 503 denge. Lambi random value daalein.")
    print(f"API: http://{settings.api_host}:{settings.api_port}   (docs: /docs)")
    uvicorn.run("app.main:app", host=settings.api_host, port=settings.api_port)


if __name__ == "__main__":
    main()
