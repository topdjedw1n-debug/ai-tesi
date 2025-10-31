"""
Structured logging with Loguru and request correlation IDs.
Security audit logging with JSON-structured events.
"""

import json
import sys
import uuid
from datetime import datetime
from typing import Optional, Any

from fastapi import Request
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware


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
    # Security audit log sink (JSON-structured, separate file)
    logger.add(
        "logs/audit.log",
        level="INFO",
        rotation="1 day",
        retention="90 days",  # Longer retention for audit logs
        backtrace=False,
        diagnose=False,
        format="{message}",
        serialize=True,  # JSON output
        filter=lambda record: record["extra"].get("audit_event") is True,
    )


def log_security_audit_event(
    event_type: str,
    correlation_id: Optional[str] = None,
    user_id: Optional[int] = None,
    ip: Optional[str] = None,
    endpoint: Optional[str] = None,
    resource: Optional[str] = None,
    action: Optional[str] = None,
    outcome: str = "success",  # success, failure, denied
    details: Optional[dict[str, Any]] = None,
) -> None:
    """
    Log a structured security audit event to audit.log.

    Args:
        event_type: Type of security event (e.g., "auth_attempt", "admin_action", "token_refresh")
        correlation_id: Request correlation ID
        user_id: User ID if authenticated
        ip: Client IP address
        endpoint: API endpoint accessed
        resource: Resource affected (e.g., "user", "document", "config")
        action: Action performed (e.g., "create", "read", "update", "delete")
        outcome: Event outcome (success, failure, denied)
        details: Additional event details
    """
    audit_event = {
        "timestamp": datetime.utcnow().isoformat(),
        "event_type": event_type,
        "correlation_id": correlation_id or "unknown",
        "user_id": user_id,
        "ip": ip,
        "endpoint": endpoint,
        "resource": resource,
        "action": action,
        "outcome": outcome,
        "details": details or {},
    }

    logger.bind(audit_event=True).info(json.dumps(audit_event))


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


