"""
Pytest configuration - sets environment variables BEFORE any imports
This ensures DATABASE_URL is set before database.py is imported
"""
import os

import pytest

# Set environment variables BEFORE any test imports
# This runs BEFORE pytest collects tests, ensuring database.py sees the correct DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
os.environ.setdefault(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
)  # Single origin for tests

from app.core.database import AsyncSessionLocal, Base, get_engine


@pytest.fixture
async def db_session():
    """Create a test database session"""
    # Create tables
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with AsyncSessionLocal() as session:
        yield session

    # Clean up after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session")
def redis_available() -> bool:
    """
    Layer 3 of Defense-in-Depth: Check if Redis is available for testing.

    Use with @pytest.mark.skipif(not redis_available) for Redis-dependent tests.

    Returns:
        bool: True if Redis is reachable, False otherwise

    See: .github/BUG_FIX_PLAN.md → Bug #1 → Layer 3
    """
    import redis.exceptions

    try:
        # Synchronous check for session-scoped fixture
        import redis

        client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        client.ping()
        client.close()
        return True
    except (redis.exceptions.ConnectionError, Exception):
        return False
