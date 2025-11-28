"""
Simple CSRF middleware requiring X-CSRF-Token for state-changing requests.
"""

from collections.abc import Callable
import os

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware


class CSRFMiddleware(BaseHTTPMiddleware):
    """Require X-CSRF-Token header for unsafe HTTP methods.

    This is a minimal protection layer for browser-based requests. For proper
    CSRF protection, pair with same-site cookies and rotating CSRF tokens.
    
    Disabled in development environment.
    """

    async def dispatch(self, request: Request, call_next: Callable):  # type: ignore[override]
        # Skip CSRF check in development
        if os.getenv("ENVIRONMENT", "development") == "development":
            return await call_next(request)
            
        if request.method.upper() in {"POST", "PUT", "PATCH", "DELETE"}:
            token = request.headers.get("X-CSRF-Token")
            if token is None or len(token) < 16:
                return Response(
                    content='{"detail":"CSRF token missing or invalid"}',
                    status_code=403,
                    media_type="application/json",
                )
        return await call_next(request)
