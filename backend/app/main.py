from contextlib import asynccontextmanager                         # lifespan (startup/shutdown) ke liye
from fastapi import Depends, FastAPI                                # FastAPI ke tools
from fastapi.middleware.cors import CORSMiddleware                  # Frontend ko ijazat dene ke liye
from app.api.auth import require_api_key                            # API key ki jaanch
from app.api.routes_health import router as health_router           # /health
from app.api.routes_incidents import router as incidents_router     # /incidents
from app.config import get_settings                                  # .env ki settings
from app.db.migrate import ensure_schema                             # Database tayyar karna


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup par database tayyar karta hai (naye columns na hon to jod deta hai). Fail ho to API phir bhi uthti hai."""
    try:
        ensure_schema()
    except Exception as error:                                       # DB abhi nahi mili - /health 503 dega
        print(f"[API] ⚠️ startup par database tayyar nahi hua: {error}")
    yield                                                             # Yahan API chalti hai


def create_app() -> FastAPI:
    """App banata hai (alag function taake tests alag settings ke sath naya app bana sakein)."""
    app = FastAPI(title="SentinelOps API", version="1.0.0", lifespan=lifespan)

    origins = [o.strip() for o in get_settings().api_cors_origins.split(",") if o.strip()]   # Frontend ke origins
    if origins:                                                        # Khali = CORS band (default)
        app.add_middleware(
            CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST"],
            allow_headers=["X-API-Key", "Content-Type"],
        )

    app.include_router(health_router)                                   # Bina key ke
    app.include_router(incidents_router, dependencies=[Depends(require_api_key)])   # Key ke sath
    return app


app = create_app()                                                      # uvicorn app.main:app yahi dhoondta hai
