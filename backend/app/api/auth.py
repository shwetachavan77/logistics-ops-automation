"""API key auth middleware. All /api/* routes require x-api-key header."""

import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

# Default key for local dev - override in production via environment variable
API_KEY = os.getenv("API_KEY", "carrier-sales-dev-key-2026")


class APIKeyMiddleware(BaseHTTPMiddleware):
    """
    Validates x-api-key header on all /api/ routes except health check.
    """

    # Routes that don't need auth
    EXEMPT_PATHS = {
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/health",
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Skip auth for exempt paths and non-API routes
        if path in self.EXEMPT_PATHS or not path.startswith("/api"):
            return await call_next(request)

        # Check for API key in header
        provided_key = request.headers.get("x-api-key")

        if not provided_key:
            raise HTTPException(
                status_code=401,
                detail="Missing x-api-key header. Include your API key in the request."
            )

        if provided_key != API_KEY:
            raise HTTPException(
                status_code=403,
                detail="Invalid API key."
            )

        return await call_next(request)
