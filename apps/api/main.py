"""
AI Thesis Platform - FastAPI Application
"""

import logging
from contextlib import asynccontextmanager
from datetime import datetime

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from loguru import logger

from app.api.v1.endpoints import (
    admin,
    admin_auth,
    admin_dashboard,
    admin_documents,
    admin_payments,
    auth,
    documents,
    generate,
    jobs,
    payment,
    pricing,
    refunds,
)
from app.api.v1.endpoints import (
    settings as settings_endpoints,
)
from app.core.config import settings
from app.core.database import init_db
from app.core.exceptions import APIException
from app.core.logging import RequestLoggingMiddleware, setup_logging
from app.core.monitoring import setup_prometheus, setup_sentry
from app.middleware.csrf import CSRFMiddleware
from app.middleware.maintenance import MaintenanceModeMiddleware
from app.middleware.rate_limit import close_redis, init_redis, setup_rate_limiter

# Configure logging
logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting AI Thesis Platform API...")
    await init_db()
    logger.info("Database initialized")
    await init_redis()
    yield
    # Shutdown
    logger.info("Shutting down AI Thesis Platform API...")
    await close_redis()


# Create FastAPI application
app = FastAPI(
    title="AI Thesis Platform API",
    description="AI-powered academic paper generation platform",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
    # redirect_slashes=True (default) - 307 redirect is standard REST API behavior
)

# Logging
setup_logging(settings.ENVIRONMENT)
app.add_middleware(RequestLoggingMiddleware)
setup_sentry(settings.ENVIRONMENT, settings.SENTRY_DSN)

# Monitoring: Prometheus metrics
setup_prometheus(app, settings.ENVIRONMENT)

# Add middleware
# CORS: restrict to explicit methods and environment-driven origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)

# Rate limiting
setup_rate_limiter(app)

# CSRF protection for state-changing requests (disabled in development)
if settings.ENVIRONMENT == "production":
    app.add_middleware(CSRFMiddleware)

# Maintenance mode middleware (should be early in the stack)
app.add_middleware(MaintenanceModeMiddleware)


# Global exception handlers
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    """Standardized API exception handler with structured error response."""
    correlation_id = request.headers.get("X-Request-ID", "unknown")
    logger.error(
        f"APIException: {exc.error_code} - {exc.detail}", correlation_id=correlation_id
    )
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error_code": exc.error_code or "UNKNOWN_ERROR",
            "detail": exc.detail,
            "status_code": exc.status_code,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    """Standardized unhandled exception handler with structured error response."""
    correlation_id = request.headers.get("X-Request-ID", "unknown")

    # Escape curly braces to prevent format string interpolation errors
    exception_str = str(exc)
    escaped_msg = exception_str.replace("{", "{{").replace("}", "}}")

    logger.exception(
        f"Unhandled exception: {type(exc).__name__} - {escaped_msg}",
        correlation_id=correlation_id,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error_code": "INTERNAL_SERVER_ERROR",
            "detail": "Internal server error",
            "status_code": 500,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "AI Thesis Platform API",
        "version": "1.0.0",
        "docs_url": "/docs",
        "health_url": "/health",
        "api_prefix": "/api/v1",
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT,
    }


# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(generate.router, prefix="/api/v1/generate", tags=["generation"])
app.include_router(jobs.router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(
    admin_dashboard.router, prefix="/api/v1/admin", tags=["admin-dashboard"]
)
app.include_router(
    admin_auth.router, prefix="/api/v1/admin/auth", tags=["admin-authentication"]
)
app.include_router(payment.router, prefix="/api/v1/payment", tags=["payment"])
app.include_router(refunds.user_router, prefix="/api/v1/refunds", tags=["refunds"])
app.include_router(
    refunds.admin_router, prefix="/api/v1/admin/refunds", tags=["admin-refunds"]
)
app.include_router(
    settings_endpoints.router, prefix="/api/v1/admin/settings", tags=["admin-settings"]
)
app.include_router(
    admin_documents.router, prefix="/api/v1/admin/documents", tags=["admin-documents"]
)
app.include_router(
    admin_payments.router, prefix="/api/v1/admin/payments", tags=["admin-payments"]
)
app.include_router(pricing.router, prefix="/api/v1/pricing", tags=["pricing"])


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=8000, reload=settings.DEBUG, log_level="info"
    )
