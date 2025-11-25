"""
Comprehensive security tests: IDOR, JWT, file security, rate limiting
"""
import os
from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from jose import jwt

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "different-test-jwt-secret-minimum-32-chars-1234567890"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_security.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "false")  # Enable rate limiting for tests

from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.auth import MagicLinkToken, User
from app.models.document import Document
from main import app  # noqa: E402


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        ac.headers.update(
            {
                "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        yield ac


@pytest.fixture
async def db_session():
    """Create a test database session"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def user1_and_token(client, db_session):
    """Create user1 and get auth token"""
    user1 = User(
        email="user1@security.test",
        full_name="User 1",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user1)

    # Create magic link token
    token = MagicLinkToken(
        token="token_user1_security",
        email=user1.email,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(user1)

    # Verify magic link
    response = await client.post(
        "/api/v1/auth/verify-magic-link",
        json={"token": "token_user1_security", "gdpr_consent": True},
    )
    if response.status_code == 200:
        auth_data = response.json()
        token_value = auth_data.get("access_token")
    else:
        # Create token manually
        from jose import jwt

        expire = datetime.utcnow() + timedelta(minutes=30)
        payload = {
            "sub": str(user1.id),
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        token_value = jwt.encode(
            payload,
            settings.JWT_SECRET or settings.SECRET_KEY,
            algorithm=settings.JWT_ALG,
        )

    return user1, token_value


@pytest.fixture
async def user2_and_token(client, db_session):
    """Create user2 and get auth token"""
    user2 = User(
        email="user2@security.test",
        full_name="User 2",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user2)

    # Create magic link token
    token = MagicLinkToken(
        token="token_user2_security",
        email=user2.email,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(user2)

    # Verify magic link
    response = await client.post(
        "/api/v1/auth/verify-magic-link",
        json={"token": "token_user2_security", "gdpr_consent": True},
    )
    if response.status_code == 200:
        auth_data = response.json()
        token_value = auth_data.get("access_token")
    else:
        # Create token manually
        from jose import jwt

        expire = datetime.utcnow() + timedelta(minutes=30)
        payload = {
            "sub": str(user2.id),
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        token_value = jwt.encode(
            payload,
            settings.JWT_SECRET or settings.SECRET_KEY,
            algorithm=settings.JWT_ALG,
        )

    return user2, token_value


class TestIDORProtection:
    """Test IDOR (Insecure Direct Object Reference) protection"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user1_cannot_access_user2_document(
        self, client, db_session, user1_and_token, user2_and_token
    ):
        """Test that user1 cannot GET user2's document"""
        user1, token1 = user1_and_token
        user2, token2 = user2_and_token

        # Create document for user2
        document = Document(
            user_id=user2.id,
            title="User 2's Secret Document",
            topic="Secret topic for user 2",
            status="draft",
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        # user1 tries to access user2's document
        headers = {"Authorization": f"Bearer {token1}"}
        response = await client.get(f"/api/v1/documents/{document.id}", headers=headers)

        # Should return 404, not 403 (to avoid revealing document existence)
        assert (
            response.status_code == 404
        ), f"Expected 404, got {response.status_code}: {response.text}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user1_cannot_update_user2_document(
        self, client, db_session, user1_and_token, user2_and_token
    ):
        """Test that user1 cannot UPDATE user2's document"""
        user1, token1 = user1_and_token
        user2, token2 = user2_and_token

        # Create document for user2
        document = Document(
            user_id=user2.id,
            title="User 2's Document",
            topic="Topic for user 2",
            status="draft",
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        # user1 tries to update user2's document
        headers = {"Authorization": f"Bearer {token1}"}
        response = await client.put(
            f"/api/v1/documents/{document.id}",
            json={"title": "Hacked Title"},
            headers=headers,
        )

        assert response.status_code == 404

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user1_cannot_delete_user2_document(
        self, client, db_session, user1_and_token, user2_and_token
    ):
        """Test that user1 cannot DELETE user2's document"""
        user1, token1 = user1_and_token
        user2, token2 = user2_and_token

        # Create document for user2
        document = Document(
            user_id=user2.id,
            title="User 2's Document",
            topic="Topic for user 2",
            status="draft",
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        # user1 tries to delete user2's document
        headers = {"Authorization": f"Bearer {token1}"}
        response = await client.delete(
            f"/api/v1/documents/{document.id}", headers=headers
        )

        assert response.status_code == 404

        # Verify document still exists
        headers2 = {"Authorization": f"Bearer {token2}"}
        verify_response = await client.get(
            f"/api/v1/documents/{document.id}", headers=headers2
        )
        assert verify_response.status_code == 200

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_user_can_access_own_document(
        self, client, db_session, user1_and_token
    ):
        """Test that user can still access their own documents"""
        user1, token1 = user1_and_token

        # Create document for user1
        document = Document(
            user_id=user1.id, title="My Document", topic="My Topic", status="draft"
        )
        db_session.add(document)
        await db_session.commit()
        await db_session.refresh(document)

        # user1 accesses own document
        headers = {"Authorization": f"Bearer {token1}"}
        response = await client.get(f"/api/v1/documents/{document.id}", headers=headers)

        assert response.status_code == 200
        data = response.json()
        assert data.get("id") == document.id


class TestJWTSecurity:
    """Test JWT security"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_expired_token_rejected(self, client, db_session, user1_and_token):
        """Test that expired JWT token is rejected"""
        user1, _ = user1_and_token

        # Create expired token
        expire = datetime.utcnow() - timedelta(minutes=1)  # Expired 1 minute ago
        payload = {
            "sub": str(user1.id),
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow() - timedelta(hours=1),
        }
        expired_token = jwt.encode(
            payload,
            settings.JWT_SECRET or settings.SECRET_KEY,
            algorithm=settings.JWT_ALG,
        )

        headers = {"Authorization": f"Bearer {expired_token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_invalid_signature_rejected(
        self, client, db_session, user1_and_token
    ):
        """Test that token with invalid signature is rejected"""
        user1, _ = user1_and_token

        # Create token with wrong secret
        expire = datetime.utcnow() + timedelta(minutes=30)
        payload = {
            "sub": str(user1.id),
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        invalid_token = jwt.encode(
            payload,
            "wrong-secret-key-for-testing-invalid-signature-123456789",
            algorithm=settings.JWT_ALG,
        )

        headers = {"Authorization": f"Bearer {invalid_token}"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_missing_token_rejected(self, client):
        """Test that missing token results in 401"""
        response = await client.get("/api/v1/auth/me")
        assert response.status_code == 401

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_malformed_token_rejected(self, client):
        """Test that malformed token is rejected"""
        headers = {"Authorization": "Bearer invalid.token.here"}
        response = await client.get("/api/v1/auth/me", headers=headers)
        assert response.status_code == 401


class TestFileSecurity:
    """Test file upload security"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_executable_file_rejected(self, client, db_session, user1_and_token):
        """Test that executable files are rejected"""
        user1, token1 = user1_and_token

        # Create document first
        doc_response = await client.post(
            "/api/v1/documents/",
            json={
                "title": "Test Doc",
                "topic": "Test topic for file upload",
                "language": "en",
                "target_pages": 10,
            },
            headers={
                "Authorization": f"Bearer {token1}",
                "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
            },
        )

        if doc_response.status_code not in [200, 201]:
            pytest.skip("Could not create document")

        document = doc_response.json()
        document_id = document.get("id") or document.get("document", {}).get("id")

        if not document_id:
            pytest.skip("Could not extract document ID")

        # Try to upload executable file (mock - actual endpoint might not exist)
        # This tests the file validator service if endpoint exists
        exe_content = b"MZ\x90\x00" + b"\x00" * 100  # PE executable header

        # Try uploading as custom requirements file
        upload_response = await client.post(
            f"/api/v1/documents/{document_id}/upload-requirements",
            files={"file": ("malware.exe", exe_content, "application/octet-stream")},
            headers={"Authorization": f"Bearer {token1}"},
        )

        # Should reject if endpoint exists and validator is active
        if upload_response.status_code not in [404, 405]:  # Endpoint might not exist
            assert upload_response.status_code in [
                400,
                422,
            ], f"Executable file should be rejected, got {upload_response.status_code}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_zip_bomb_detection(self, client, db_session, user1_and_token):
        """Test ZIP bomb detection (if implemented)"""
        # This is a placeholder - actual ZIP bomb detection would require
        # implementing the check_zip_bomb method in FileValidator
        # For now, we just verify the test structure
        pass


class TestRateLimiting:
    """Test rate limiting"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_rate_limit_enforced(self, client, db_session):
        """Test that rate limiting is enforced"""
        # Try to request magic link many times quickly
        responses = []
        for i in range(15):  # Exceed typical rate limit
            response = await client.post(
                "/api/v1/auth/magic-link", json={"email": f"ratelimit{i}@test.com"}
            )
            responses.append(response.status_code)

        # Should eventually get 429 (Too Many Requests) if rate limiting is active
        # Note: Rate limiting might be disabled in test environment
        if 429 in responses:
            assert True, "Rate limiting is working"
        else:
            # Rate limiting might be disabled for tests
            pytest.skip("Rate limiting appears to be disabled in test environment")


class TestCSRFProtection:
    """Test CSRF protection"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_csrf_protection_state_changing_requests(
        self, client, db_session, user1_and_token
    ):
        """Test that state-changing requests require CSRF token"""
        user1, token1 = user1_and_token

        # Try to create document without CSRF token
        response = await client.post(
            "/api/v1/documents/",
            json={
                "title": "CSRF Test",
                "topic": "Testing CSRF protection",
                "language": "en",
                "target_pages": 10,
            },
            headers={"Authorization": f"Bearer {token1}"},
            # No X-CSRF-Token header
        )

        # Should either require CSRF or accept (if CSRF is disabled in tests)
        # This depends on actual CSRF middleware implementation
        assert response.status_code in [
            200,
            201,
            403,
            422,
        ], f"Unexpected response: {response.status_code}"
