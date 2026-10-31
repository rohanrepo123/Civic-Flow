"""CivicFlow Core API — Member 1's main application.

Owns: authentication, database, applications, service registry,
orchestration between AI and Browser services, and the frontend API contract.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api import router as api_router
from app.db.health import dependency_health, close_connections
from fastapi import HTTPException


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle."""
    # Startup — connect to DB, Redis, verify downstream service health
    print(f"[core_api] Starting CivicFlow Core API v{settings.APP_VERSION}")
    yield
    # Shutdown — close pools
    await close_connections()
    print("[core_api] Shutting down Core API")


app = FastAPI(
    title="CivicFlow Core API",
    version=settings.APP_VERSION,
    description="Core backend for CivicFlow — auth, applications, orchestration.",
    lifespan=lifespan,
)

# CORS — allow the Next.js frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount all API routes
app.include_router(api_router)


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.get("/health/live", tags=["health"])
async def liveness():
    return {"status": "alive", "service": "core_api"}


@app.get("/health/ready", tags=["health"])
async def readiness():
    dependencies = await dependency_health()
    ready = all(value in {"ready", "not_required"} for value in dependencies.values())
    if not ready:
        raise HTTPException(status_code=503, detail={"status": "not_ready", "service": "core_api", "dependencies": dependencies})
    return {"status": "ready", "service": "core_api", "version": settings.APP_VERSION, "dependencies": dependencies}
