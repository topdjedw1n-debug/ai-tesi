"""
Maintenance mode middleware
"""

from fastapi import Request, status
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.database import AsyncSessionLocal
from app.services.settings_service import SettingsService


class MaintenanceModeMiddleware(BaseHTTPMiddleware):
    """
    Middleware to check maintenance mode.

    If maintenance mode is enabled:
    - Blocks all requests except admin endpoints
    - Allows IPs in whitelist
    - Returns 503 Service Unavailable with maintenance message
    """

    async def dispatch(self, request: Request, call_next):
        # Skip maintenance check for admin endpoints
        if request.url.path.startswith("/api/v1/admin"):
            # Admin endpoints are allowed during maintenance
            response = await call_next(request)
            return response

        # Skip health check endpoint
        if request.url.path in ["/health", "/"]:
            response = await call_next(request)
            return response

        # Check maintenance mode
        try:
            async with AsyncSessionLocal() as db:
                service = SettingsService(db)
                is_maintenance = await service.is_maintenance_enabled()

                if is_maintenance:
                    # Check if IP is whitelisted
                    client_ip = request.client.host if request.client else None
                    allowed_ips = await service.get_maintenance_allowed_ips()

                    # If whitelist is empty, allow all IPs
                    # If whitelist has IPs, check if client IP is in it
                    if allowed_ips and client_ip and client_ip not in allowed_ips:
                        # IP not whitelisted - return maintenance message
                        message = await service.get_maintenance_message()
                        return JSONResponse(
                            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                            content={
                                "detail": message,
                                "maintenance_mode": True,
                            },
                        )
        except Exception:
            # If there's an error checking maintenance mode, allow request
            # This prevents maintenance mode from breaking the entire system
            pass

        # Continue with request
        response = await call_next(request)
        return response
