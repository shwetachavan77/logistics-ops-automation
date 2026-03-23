"""Carrier Sales API - FastAPI backend for HappyRobot voice agent."""

from contextlib import asynccontextmanager
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.api.routes import router, limiter
from app.api.auth import APIKeyMiddleware
from app.db.database import Database


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Startup/shutdown lifecycle.
    - Connect to PostgreSQL and create tables on boot
    - Seed sample load data (and demo call data if DEMO_MODE=true)
    - Clean disconnect on shutdown
    """
    await Database.connect()
    await Database.seed_loads()

    # In demo mode, also seed fake call data for the dashboard
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

# CORS - allow the React dashboard and HappyRobot to call us
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, lock this to specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(APIKeyMiddleware)

# Mount all routes
app.include_router(router)


@app.get("/")
async def root():
    return {
        "service": "HappyRobot Carrier Sales API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }
