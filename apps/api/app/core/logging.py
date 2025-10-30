"""
Structured logging with Loguru and request correlation IDs.
"""

from typing import Optional
import sys
import uuid
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request


def setup_logging(environment: str = "development") -> None:
    """Configure Loguru sinks, formats, and rotation."""
    logger.remove()
    log_level = "DEBUG" if environment != "production" else "INFO"
    # Console sink
    logger.add(sys.stdout, level=log_level, backtrace=False, diagnose=False,
               format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[correlation_id]} | {message}")
    # File sink with rotation/retention
    logger.add(
        "logs/app.log",
        level=log_level,
        rotation="1 day",
        retention="30 days",
        backtrace=False,
        diagnose=False,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level} | {extra[correlation_id]} | {message}",
    )


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to add correlation ID and log request/response lifecycle."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        correlation_id: str = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        with logger.contextualize(correlation_id=correlation_id):
            logger.info(f"HTTP {request.method} {request.url.path}")
            response = await call_next(request)
            response.headers["X-Request-ID"] = correlation_id
            logger.info(f"{response.status_code} {request.method} {request.url.path}")
            return response


