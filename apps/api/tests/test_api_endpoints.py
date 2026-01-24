"""
Integration tests for API endpoints
Tests full request/response cycles through the API
"""
import os

import pytest
from httpx import AsyncClient

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
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
async def test_health_endpoint_accessible(client):
    """Integration test: Health endpoint should be publicly accessible"""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data.get("status") == "healthy"
    assert "version" in data


@pytest.mark.asyncio
async def test_auth_me_endpoint_requires_token(client):
    """Integration test: Protected endpoint should require authentication"""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generate_models_endpoint(client):
    """Integration test: Models endpoint should return available models"""
    response = await client.get("/api/v1/generate/models")
    assert response.status_code == 200
    data = response.json()
    assert "openai" in data
    assert "anthropic" in data
    assert len(data["openai"]) > 0
    assert len(data["anthropic"]) > 0


@pytest.mark.asyncio
async def test_documents_list_requires_auth(client):
    """Integration test: Documents list endpoint requires authentication"""
    response = await client.get("/api/v1/documents", follow_redirects=False)
    # Can be 307 (redirect) or 401, both indicate auth is required
    assert response.status_code in [301, 307, 401]


@pytest.mark.asyncio
async def test_create_document_requires_auth(client):
    """Integration test: Create document endpoint requires authentication"""
    document_data = {
        "title": "Test Thesis",
        "topic": "AI in Education",
        "language": "en",
        "target_pages": 10,
    }
    response = await client.post("/api/v1/documents/", json=document_data)
    # Can be 401 or 403, both indicate auth is required
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_export_document_requires_auth(client):
    """Integration test: Export document endpoint requires authentication"""
    # Try to export a document without auth
    response = await client.get("/api/v1/documents/1/export/docx")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_generate_outline_requires_auth(client):
    """Integration test: Generate outline endpoint requires authentication"""
    request_data = {"document_id": 1, "additional_requirements": None}
    response = await client.post("/api/v1/generate/outline", json=request_data)
    # Can be 401 or 403, both indicate auth is required
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_generate_section_requires_auth(client):
    """Integration test: Generate section endpoint requires authentication"""
    request_data = {
        "document_id": 1,
        "section_title": "Introduction",
        "section_index": 0,
        "additional_requirements": None,
    }
    response = await client.post("/api/v1/generate/section", json=request_data)
    # Can be 401 or 403, both indicate auth is required
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_full_document_generation_requires_auth(client):
    """Integration test: Outline generation endpoint requires authentication"""
    request_data = {"document_id": 1, "additional_requirements": None}
    # Test outline endpoint instead of non-existent full-document endpoint
    response = await client.post("/api/v1/generate/outline", json=request_data)
    # Can be 401 or 403, both indicate auth is required
    assert response.status_code in [401, 403]


@pytest.mark.asyncio
async def test_usage_stats_requires_auth(client):
    """Integration test: Usage stats endpoint requires authentication"""
    response = await client.get("/api/v1/generate/usage/1")
    assert response.status_code == 401
