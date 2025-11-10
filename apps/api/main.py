"""
AI Thesis Platform - FastAPI Application
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
import uvicorn
import logging
from contextlib import asynccontextmanager
import os

from app.core.config import settings
from app.core.database import init_db
from app.api.v1.endpoints import generate, auth, admin, documents, payment
from app.core.exceptions import APIException
from app.middleware.rate_limit import setup_rate_limiter
from app.middleware.csrf import CSRFMiddleware
from app.core.logging import setup_logging, RequestLoggingMiddleware
from app.core.monitoring import setup_sentry

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events"""
    # Startup
    logger.info("Starting AI Thesis Platform API...")
    await init_db()
    logger.info("Database initialized")
    yield
    # Shutdown
    logger.info("Shutting down AI Thesis Platform API...")


# Create FastAPI application
app = FastAPI(
    title="AI Thesis Platform API",
    description="AI-powered academic paper generation platform",
    version="1.0.0",
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Logging
setup_logging(settings.ENVIRONMENT)
app.add_middleware(RequestLoggingMiddleware)
setup_sentry(settings.ENVIRONMENT, settings.SENTRY_DSN)

# Monitoring (Sentry) is initialized via setup_sentry above

# Add middleware
# CORS: restrict to explicit methods and environment-driven origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Requested-With"],
)

app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=settings.ALLOWED_HOSTS
)

# Rate limiting
setup_rate_limiter(app)

# CSRF protection for state-changing requests
app.add_middleware(CSRFMiddleware)

# Global exception handlers
@app.exception_handler(APIException)
async def api_exception_handler(request: Request, exc: APIException):
    logging.getLogger(__name__).error(f"APIException: {exc.error_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "error_code": exc.error_code}
    )

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logging.getLogger(__name__).exception("Unhandled exception")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
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
        "api_prefix": "/api/v1"
    }

# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "version": "1.0.0",
        "environment": settings.ENVIRONMENT
    }


# Include API routers
app.include_router(auth.router, prefix="/api/v1/auth", tags=["authentication"])
app.include_router(generate.router, prefix="/api/v1/generate", tags=["generation"])
app.include_router(documents.router, prefix="/api/v1/documents", tags=["documents"])
app.include_router(admin.router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(payment.router, prefix="/api/v1/payment", tags=["payment"])


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
