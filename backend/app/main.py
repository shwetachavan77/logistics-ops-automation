"""Carrier Sales API - FastAPI backend for HappyRobot voice agent."""

from contextlib import asynccontextmanager
import os
from pathlib import Path
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.routes import router, limiter
from app.api.auth import APIKeyMiddleware
from app.db.database import Database

STATIC_DIR = Path(__file__).parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    await Database.connect()
    await Database.seed_loads()

    if os.getenv("DEMO_MODE", "true").lower() == "true":
        from app.db.seed_calls import seed_demo_calls
        await seed_demo_calls()

    print("Carrier Sales API is ready")
    yield
    await Database.disconnect()


app = FastAPI(
    title="Carrier Sales API",
    description=(
        "Backend for HappyRobot's inbound carrier sales agent. "
        "Handles FMCSA verification, load matching, negotiation, "
        "and call analytics."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(APIKeyMiddleware)

app.include_router(router)


@app.get("/")
async def dashboard():
    """Serve the metrics dashboard."""
    html_path = STATIC_DIR / "index.html"
    if html_path.exists():
        return FileResponse(html_path, media_type="text/html")
    return {"message": "Dashboard not found. Check /docs for API."}
