import hmac                                                       # hmac.compare_digest - timing-safe compare
from fastapi import Header, HTTPException                         # Header - request header padhne ke liye
from app.config import get_settings                                # .env ki settings


def require_api_key(x_api_key: str = Header(default="", alias="X-API-Key")) -> None:
    """Dependency: sahi key ho to kuch nahi karta, warna HTTPException uthata hai."""
    configured = get_settings().api_key                            # Server ki asli key (.env)
    if not configured:                                              # Server par key set hi nahi
        raise HTTPException(status_code=503, detail="API_KEY server par set nahi hai (.env me API_KEY daalein)")
    # compare_digest: key ko character-by-character jaldi-jaldi nahi, barabar waqt me compare karta hai
    if not hmac.compare_digest(x_api_key.encode("utf-8"), configured.encode("utf-8")):
        raise HTTPException(status_code=401, detail="API key galat ya missing hai (header: X-API-Key)")
