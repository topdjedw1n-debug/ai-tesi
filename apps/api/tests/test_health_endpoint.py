"""
Smoke test: Health endpoint
Tests: GET /health → status 200
"""
import pytest
import os

# Set environment variables for tests (required by config validation)
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from httpx import AsyncClient
from main import app


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """Smoke test: Health endpoint should return 200 OK"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "healthy"
    assert "version" in data
    assert "environment" in data

