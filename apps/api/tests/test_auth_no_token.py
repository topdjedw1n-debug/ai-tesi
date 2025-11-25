"""
Smoke test: Auth endpoint without token
Tests: GET /api/v1/auth/me without token → status 401
"""
import os

import pytest
from httpx import AsyncClient

# Set environment variables for tests (required by config validation)
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from main import app  # noqa: E402


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_auth_no_token(client):
    """Smoke test: Protected endpoint should return 401 without valid token"""
    # Attempt to access protected endpoint without token
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
