"""API key auth middleware. All /api/* POST routes require x-api-key header."""

import os
from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware

API_KEY = os.getenv("API_KEY", "carrier-sales-dev-key-2026")


class APIKeyMiddleware(BaseHTTPMiddleware):

    EXEMPT_PATHS = {
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/health",
    }

    # GET endpoints the dashboard needs without auth
    DASHBOARD_PATHS = {
        "/api/metrics",
        "/api/calls/recent",
        "/api/loads",
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in self.EXEMPT_PATHS or not path.startswith("/api"):
            return await call_next(request)

        # Allow dashboard GET requests without auth
        if request.method == "GET" and path in self.DASHBOARD_PATHS:
            return await call_next(request)

        provided_key = request.headers.get("x-api-key")

        if not provided_key:
            raise HTTPException(
                status_code=401,
                detail="Missing x-api-key header."
            )

        if provided_key != API_KEY:
            raise HTTPException(
                status_code=403,
                detail="Invalid API key."
            )

        return await call_next(request)
