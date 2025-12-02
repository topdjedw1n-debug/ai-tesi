"""
Middleware for checking admin IP whitelist
"""

import logging
from collections.abc import Callable

from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.core.config import settings

logger = logging.getLogger(__name__)


class AdminIPCheckMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check IP whitelist for admin endpoints.

    Only applies to /api/v1/admin/* endpoints.
    If ADMIN_IP_WHITELIST is configured, only allows listed IPs.
    If not configured (empty), all IPs are allowed.
    """

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Only check admin endpoints
        if request.url.path.startswith("/api/v1/admin"):
            # Skip check if whitelist is not configured
            if settings.ADMIN_IP_WHITELIST:
                allowed_ips = [
                    ip.strip()
                    for ip in settings.ADMIN_IP_WHITELIST.split(",")
                    if ip.strip()
                ]

                if allowed_ips:
                    client_ip = request.client.host if request.client else None

                    if not client_ip or client_ip not in allowed_ips:
                        logger.warning(
                            f"Admin access denied from IP: {client_ip}, "
                            f"path: {request.url.path}"
                        )
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail="IP address not whitelisted for admin access",
                        )

        response = await call_next(request)
        return response

