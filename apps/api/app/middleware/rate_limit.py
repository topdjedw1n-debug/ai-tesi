"""
Rate limiting middleware and utilities using SlowAPI with Redis storage.
Implements per-user/IP rate limiting with failed auth attempt tracking.
"""

import logging
from collections.abc import Callable
from datetime import datetime, timedelta

import redis.asyncio as aioredis
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import settings

logger = logging.getLogger(__name__)

# Redis client (initialized on startup)
_redis_client: aioredis.Redis | None = None


def get_redis_client() -> aioredis.Redis | None:
    """Get Redis client, or None if Redis is unavailable"""
    global _redis_client
    return _redis_client


async def init_redis() -> None:
    """Initialize Redis connection (called on startup)"""
    global _redis_client
    try:
        if settings.ENVIRONMENT.lower() in {"production", "prod"}:
            # Production: require Redis
            _redis_client = await aioredis.from_url(
                settings.REDIS_URL,
                decode_responses=True,
                socket_connect_timeout=5,
                socket_timeout=5
            )
            await _redis_client.ping()
            logger.info("Redis connected for rate limiting")
        else:
            # Development: try Redis, fall back to memory if unavailable
            try:
                _redis_client = await aioredis.from_url(
                    settings.REDIS_URL,
                    decode_responses=True,
                    socket_connect_timeout=2,
                    socket_timeout=2
                )
                await _redis_client.ping()
                logger.info("Redis connected for rate limiting")
            except Exception:
                logger.warning("Redis unavailable, using memory-based rate limiting")
                _redis_client = None
    except Exception as e:
        logger.error(f"Failed to connect to Redis: {e}")
        if settings.ENVIRONMENT.lower() in {"production", "prod"}:
            raise  # Fail fast in production
        _redis_client = None


async def close_redis() -> None:
    """Close Redis connection (called on shutdown)"""
    global _redis_client
    if _redis_client:
        await _redis_client.close()
        _redis_client = None
        logger.info("Redis connection closed")


def get_user_id_or_ip(request: Request) -> str:
    """
    Get rate limit key: user ID if authenticated, otherwise IP address.
    This enables per-user rate limiting for authenticated requests.
    """
    # Try to get current user from request state (set by dependency)
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fall back to IP address
    return get_remote_address(request)


async def check_auth_lockout(identifier: str) -> timedelta | None:
    """
    Check if identifier (user or IP) is locked out due to failed auth attempts.
    Returns lockout duration if locked, None otherwise.
    """
    redis_client = get_redis_client()
    if not redis_client:
        return None  # No Redis, no lockout tracking

    try:
        failed_attempts_key = f"auth_failed:{identifier}"
        lockout_key = f"auth_locked:{identifier}"

        # Check if currently locked
        lockout_until = await redis_client.get(lockout_key)
        if lockout_until:
            lockout_time = datetime.fromisoformat(lockout_until)
            if datetime.utcnow() < lockout_time:
                remaining = lockout_time - datetime.utcnow()
                logger.warning(
                    f"AUTH_LOCKOUT_ACTIVE: identifier={identifier}, "
                    f"remaining_minutes={int(remaining.total_seconds() / 60)}"
                )
                return remaining
            else:
                # Lockout expired, clear it
                await redis_client.delete(lockout_key)

        # Check failed attempts count
        failed_count = await redis_client.get(failed_attempts_key)
        if failed_count:
            count = int(failed_count)
            threshold = settings.RATE_LIMIT_AUTH_LOCKOUT_THRESHOLD
            min_lockout = settings.RATE_LIMIT_AUTH_LOCKOUT_MIN_MINUTES
            max_lockout = settings.RATE_LIMIT_AUTH_LOCKOUT_MAX_MINUTES
            if count >= threshold:
                # Apply lockout: progressive (15-30 minutes)
                # More attempts = longer lockout
                lockout_minutes = min(min_lockout + (count - threshold) * 3, max_lockout)
                lockout_until = datetime.utcnow() + timedelta(minutes=lockout_minutes)
                await redis_client.setex(
                    lockout_key,
                    int(lockout_minutes * 60),
                    lockout_until.isoformat()
                )
                logger.warning(
                    f"AUTH_LOCKOUT_APPLIED: identifier={identifier}, "
                    f"lockout_minutes={lockout_minutes}, failed_attempts={count}"
                )
                return timedelta(minutes=lockout_minutes)
    except Exception as e:
        logger.error(f"Error checking auth lockout: {e}")

    return None


async def record_auth_failure(identifier: str) -> None:
    """Record a failed authentication attempt"""
    redis_client = get_redis_client()
    if not redis_client:
        return  # No Redis, no tracking

    try:
        failed_attempts_key = f"auth_failed:{identifier}"
        # Increment counter, expire after 1 hour
        await redis_client.incr(failed_attempts_key)
        await redis_client.expire(failed_attempts_key, 3600)  # 1 hour window

        failed_count = await redis_client.get(failed_attempts_key)
        logger.warning(
            f"AUTH_FAILURE_RECORDED: identifier={identifier}, "
            f"failed_count={failed_count}, threshold={settings.RATE_LIMIT_AUTH_LOCKOUT_THRESHOLD}"
        )
    except Exception as e:
        logger.error(f"Error recording auth failure: {e}")


async def clear_auth_failures(identifier: str) -> None:
    """Clear failed auth attempts on successful authentication"""
    redis_client = get_redis_client()
    if not redis_client:
        return

    try:
        failed_attempts_key = f"auth_failed:{identifier}"
        lockout_key = f"auth_locked:{identifier}"
        await redis_client.delete(failed_attempts_key)
        await redis_client.delete(lockout_key)
        logger.info(f"Auth failures cleared for {identifier}")
    except Exception as e:
        logger.error(f"Error clearing auth failures: {e}")


# Custom key function for SlowAPI
def rate_limit_key_func(request: Request) -> str:
    """Key function for rate limiting: user ID or IP"""
    return get_user_id_or_ip(request)


# Global limiter instance (lazy initialization)
_limiter: Limiter | None = None


def get_limiter() -> Limiter | None:
    """Get rate limiter instance (lazy initialization, defensive)"""
    global _limiter

    # Check if rate limiting is disabled
    if settings.DISABLE_RATE_LIMIT:
        return None

    # Lazy initialization: only create if not already created
    if _limiter is None:
        try:
            is_prod = settings.ENVIRONMENT.lower() in {"production", "prod"}

            # Determine storage configuration
            storage_uri: str | None = None
            storage_options: dict | None = None

            if is_prod:
                # Production: use Redis
                storage_uri = settings.REDIS_URL
                storage_options = {"decode_responses": True}
            else:
                # Development: try Redis if available, otherwise memory (None)
                # Let SlowAPI handle None as memory storage
                try:
                    # Test Redis availability
                    import redis.asyncio  # noqa: F401
                    # We'll defer actual connection test to init_redis
                    storage_uri = settings.REDIS_URL
                    storage_options = {"decode_responses": True}
                except ImportError:
                    # Redis not available, use memory
                    storage_uri = None
                    storage_options = None

            _limiter = Limiter(
                key_func=rate_limit_key_func,
                default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
                storage_uri=storage_uri,
                storage_options=storage_options,
            )
            logger.info(f"Rate limiter initialized (storage={'Redis' if storage_uri else 'memory'})")
        except Exception as e:
            logger.error(f"Failed to initialize rate limiter: {e}, falling back to disabled")
            _limiter = None

    return _limiter


def setup_rate_limiter(app: FastAPI) -> None:
    """
    Attach rate limiter and handlers to the FastAPI app.

    Registers the limiter, adds middleware, and configures JSON handlers for
    429 responses and auth lockouts. Defensive: gracefully handles disabled or failed initialization.
    """
    limiter_instance = get_limiter()

    # Only setup if limiter is available
    if limiter_instance is None:
        logger.warning("Rate limiting is disabled or failed to initialize")
        app.state.limiter = None
        return

    try:
        app.state.limiter = limiter_instance
        app.add_middleware(SlowAPIMiddleware)

        @app.exception_handler(RateLimitExceeded)
        async def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded):  # type: ignore[override]
            """Handle rate limit exceeded (429) with audit logging"""
            identifier = get_user_id_or_ip(request)
            endpoint = request.url.path
            ip_address = request.client.host if request.client else "unknown"
            logger.warning(
                f"RATE_LIMIT_EXCEEDED: endpoint={endpoint}, identifier={identifier}, "
                f"ip={ip_address}, limit={exc.limit if hasattr(exc, 'limit') else 'unknown'}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": "Rate limit exceeded. Please try again later.",
                    "limit": str(exc.limit) if getattr(exc, "limit", None) else None,
                },
            )
    except Exception as e:
        logger.error(f"Failed to setup rate limiter middleware: {e}, continuing without rate limiting")
        app.state.limiter = None

    # Note: Redis cleanup is handled in main.py lifespan shutdown


# Safe rate limit decorator that handles None limiter gracefully
def rate_limit(limit: str) -> Callable:
    """
    Decorator factory for rate limiting endpoints.
    Safely handles disabled or unavailable rate limiter.

    Usage:
        @rate_limit("10/hour")
        async def my_endpoint(...):
            ...
    """
    def decorator(func: Callable) -> Callable:
        limiter_instance = get_limiter()
        if limiter_instance is None:
            # Rate limiting disabled or unavailable, return original function
            return func
        # Apply rate limit decorator
        return limiter_instance.limit(limit)(func)
    return decorator


# Export limiter for backward compatibility (will be None if disabled)
# Prefer using rate_limit() decorator instead
limiter = get_limiter()


# Decorator for auth endpoints with lockout checking
def check_auth_lockout_middleware(endpoint_func: Callable) -> Callable:
    """Middleware decorator to check auth lockout before endpoint execution"""
    async def wrapper(request: Request, *args, **kwargs):
        identifier = get_user_id_or_ip(request)
        lockout = await check_auth_lockout(identifier)
        if lockout:
            logger.warning(
                f"Auth endpoint access denied due to lockout: {identifier}, "
                f"remaining: {lockout}"
            )
            return JSONResponse(
                status_code=429,
                content={
                    "detail": f"Account temporarily locked due to multiple failed authentication attempts. "
                             f"Please try again in {int(lockout.total_seconds() / 60)} minutes.",
                    "lockout_remaining_minutes": int(lockout.total_seconds() / 60),
                },
            )
        return await endpoint_func(request, *args, **kwargs)
    return wrapper
