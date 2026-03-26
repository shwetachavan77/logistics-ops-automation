"""API key auth middleware. All /api/* routes require x-api-key header."""

import os
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

API_KEY = os.getenv("API_KEY", "carrier-sales-dev-key-2026")
DASHBOARD_PASSWORD = os.getenv("DASHBOARD_PASSWORD", "0happyrobot")


class APIKeyMiddleware(BaseHTTPMiddleware):

    EXEMPT_PATHS = {
        "/",
        "/docs",
        "/openapi.json",
        "/redoc",
        "/api/health",
        "/api/auth/login",
    }

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        if path in self.EXEMPT_PATHS or not path.startswith("/api"):
            return await call_next(request)

        provided_key = request.headers.get("x-api-key")

        if not provided_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Missing x-api-key header."}
            )

        if provided_key != API_KEY:
            return JSONResponse(
                status_code=403,
                content={"detail": "Invalid API key."}
            )

        return await call_next(request)
