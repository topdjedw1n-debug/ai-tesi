"""
Rate limiting middleware and utilities using SlowAPI.
"""

from typing import Callable
from fastapi import FastAPI
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from fastapi.responses import JSONResponse


# Global limiter instance with a safe general default
limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"])


def setup_rate_limiter(app: FastAPI) -> None:
    """Attach rate limiter and handlers to the FastAPI app.

    Registers the limiter, adds middleware, and configures a JSON handler for
    429 responses.
    """

    app.state.limiter = limiter
    app.add_middleware(SlowAPIMiddleware)

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_exceeded_handler(request, exc: RateLimitExceeded):  # type: ignore[override]
        return JSONResponse(
            status_code=429,
            content={
                "detail": "Rate limit exceeded. Please try again later.",
                "limit": str(exc.limit) if getattr(exc, "limit", None) else None,
            },
        )


