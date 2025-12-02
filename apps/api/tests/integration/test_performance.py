"""
Performance tests: concurrent users, large documents, memory monitoring
"""
import asyncio
import os
import time
from datetime import datetime, timedelta

import psutil
import pytest
from httpx import AsyncClient

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ.get("SECRET_KEY"))
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_performance.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
os.environ.setdefault("OPENAI_API_KEY", "sk-test-mock-key")

from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.auth import MagicLinkToken, User
from main import app  # noqa: E402


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test", timeout=30.0) as ac:
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
async def auth_token(client, db_session):
    """Create authenticated user and return token"""
    user = User(
        email="perf_test@example.com",
        full_name="Performance Test User",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)

    token = MagicLinkToken(
        token="token_perf_test",
        email=user.email,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    db_session.add(token)
    await db_session.commit()
    await db_session.refresh(user)

    response = await client.post(
        "/api/v1/auth/verify-magic-link",
        json={"token": "token_perf_test", "gdpr_consent": True},
    )

    if response.status_code == 200:
        return response.json().get("access_token")
    else:
        from jose import jwt

        from app.core.config import settings

        expire = datetime.utcnow() + timedelta(minutes=30)
        payload = {
            "sub": str(user.id),
            "type": "access",
            "exp": expire,
            "iat": datetime.utcnow(),
        }
        return jwt.encode(
            payload,
            settings.JWT_SECRET or settings.SECRET_KEY,
            algorithm=settings.JWT_ALG,
        )


class TestConcurrentUsers:
    """Test concurrent user operations"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_concurrent_document_creation(self, client, db_session):
        """Test creating documents concurrently (10 users)"""
        # Create multiple users with tokens
        users_and_tokens = []
        for i in range(10):
            user = User(
                email=f"concurrent_user_{i}@test.com",
                full_name=f"Concurrent User {i}",
                is_active=True,
                is_verified=True,
            )
            db_session.add(user)

            token_obj = MagicLinkToken(
                token=f"token_concurrent_{i}",
                email=user.email,
                expires_at=datetime.utcnow() + timedelta(minutes=30),
            )
            db_session.add(token_obj)

            # Create token manually for speed
            from jose import jwt

            from app.core.config import settings

            await db_session.commit()
            await db_session.refresh(user)

            expire = datetime.utcnow() + timedelta(minutes=30)
            payload = {
                "sub": str(user.id),
                "type": "access",
                "exp": expire,
                "iat": datetime.utcnow(),
            }
            token = jwt.encode(
                payload,
                settings.JWT_SECRET or settings.SECRET_KEY,
                algorithm=settings.JWT_ALG,
            )
            users_and_tokens.append((user, token))

        # Concurrent document creation
        async def create_document(user_data):
            user, token = user_data
            headers = {
                "Authorization": f"Bearer {token}",
                "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
            }
            response = await client.post(
                "/api/v1/documents/",
                json={
                    "title": f"Document for {user.email}",
                    "topic": f"Research topic for concurrent test user {user.id}",
                    "language": "en",
                    "target_pages": 10,
                },
                headers=headers,
            )
            return response.status_code, user.id

        # Execute concurrently
        start_time = time.time()
        tasks = [create_document(user_data) for user_data in users_and_tokens]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = time.time()

        # Verify results
        success_count = sum(
            1 for r in results if isinstance(r, tuple) and r[0] in [200, 201]
        )
        assert (
            success_count >= 8
        ), f"Expected at least 8 successful creations, got {success_count}"

        # Verify reasonable performance (should complete in reasonable time)
        elapsed = end_time - start_time
        assert elapsed < 10, f"Concurrent operations took too long: {elapsed}s"
        print(
            f"Concurrent document creation: {success_count}/10 successful in {elapsed:.2f}s"
        )

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_concurrent_document_listing(self, client, db_session, auth_token):
        """Test concurrent document listing requests"""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Create some documents first
        for i in range(5):
            await client.post(
                "/api/v1/documents/",
                json={
                    "title": f"Doc {i}",
                    "topic": f"Topic {i} with sufficient length for validation",
                    "language": "en",
                    "target_pages": 10,
                },
                headers={
                    **headers,
                    "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
                },
            )

        # Concurrent listing requests
        async def list_documents():
            response = await client.get("/api/v1/documents/", headers=headers)
            return response.status_code, response.json()

        start_time = time.time()
        tasks = [list_documents() for _ in range(20)]
        results = await asyncio.gather(*tasks)
        end_time = time.time()

        # All should succeed
        success_count = sum(1 for r in results if r[0] == 200)
        assert (
            success_count == 20
        ), f"Expected all 20 requests to succeed, got {success_count}"

        elapsed = end_time - start_time
        print(
            f"Concurrent listing: 20 requests in {elapsed:.2f}s ({20/elapsed:.1f} req/s)"
        )


class TestLargeDocuments:
    """Test handling of large documents"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_large_document_metadata(self, client, db_session, auth_token):
        """Test creating document with large metadata"""
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
        }

        # Create document with large title and topic
        large_title = "A" * 500  # Max title length
        large_topic = "B" * 500  # Max topic length

        response = await client.post(
            "/api/v1/documents/",
            json={
                "title": large_title,
                "topic": large_topic,
                "language": "en",
                "target_pages": 200,  # Large document
            },
            headers=headers,
        )

        # Should either accept or reject with validation error
        assert response.status_code in [
            200,
            201,
            422,
        ], f"Unexpected status for large document: {response.status_code}"

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_many_documents_cleanup(self, client, db_session, auth_token):
        """Test creating and deleting many documents"""
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
        }

        # Create 50 documents
        document_ids = []
        for i in range(50):
            response = await client.post(
                "/api/v1/documents/",
                json={
                    "title": f"Bulk Doc {i}",
                    "topic": f"Topic {i} for bulk operations testing",
                    "language": "en",
                    "target_pages": 10,
                },
                headers=headers,
            )
            if response.status_code in [200, 201]:
                doc = response.json()
                doc_id = doc.get("id") or doc.get("document", {}).get("id")
                if doc_id:
                    document_ids.append(doc_id)

        print(f"Created {len(document_ids)} documents")

        # Verify we can list them
        list_response = await client.get("/api/v1/documents/", headers=headers)
        assert list_response.status_code == 200

        # Delete all
        delete_count = 0
        for doc_id in document_ids:
            del_response = await client.delete(
                f"/api/v1/documents/{doc_id}", headers=headers
            )
            if del_response.status_code == 200:
                delete_count += 1

        print(f"Deleted {delete_count}/{len(document_ids)} documents")
        assert delete_count == len(document_ids)


class TestMemoryMonitoring:
    """Test memory usage monitoring"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_memory_usage_document_operations(
        self, client, db_session, auth_token
    ):
        """Monitor memory usage during document operations"""
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
        }

        process = psutil.Process()
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Create multiple documents
        for i in range(20):
            response = await client.post(
                "/api/v1/documents/",
                json={
                    "title": f"Memory Test Doc {i}",
                    "topic": f"Memory testing topic {i}",
                    "language": "en",
                    "target_pages": 10,
                },
                headers=headers,
            )
            # Process response to ensure it's consumed
            if response.status_code in [200, 201]:
                _ = response.json()

        peak_memory = process.memory_info().rss / 1024 / 1024  # MB

        # Force garbage collection
        import gc

        gc.collect()

        final_memory = process.memory_info().rss / 1024 / 1024  # MB

        print(
            f"Memory usage: Initial={initial_memory:.1f}MB, Peak={peak_memory:.1f}MB, Final={final_memory:.1f}MB"
        )

        # Memory should not grow excessively (allowing for reasonable overhead)
        memory_growth = final_memory - initial_memory
        assert (
            memory_growth < 100
        ), f"Memory grew by {memory_growth:.1f}MB, which is excessive"

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_response_time_list_documents(self, client, db_session, auth_token):
        """Test response time for listing documents"""
        headers = {"Authorization": f"Bearer {auth_token}"}

        # Create some documents
        for i in range(10):
            await client.post(
                "/api/v1/documents/",
                json={
                    "title": f"Response Time Doc {i}",
                    "topic": f"Topic {i} for response time testing",
                    "language": "en",
                    "target_pages": 10,
                },
                headers={
                    **headers,
                    "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
                },
            )

        # Measure response time
        start_time = time.time()
        response = await client.get("/api/v1/documents/", headers=headers)
        end_time = time.time()

        elapsed = end_time - start_time
        print(f"Document listing response time: {elapsed*1000:.1f}ms")

        assert response.status_code == 200
        assert elapsed < 2.0, f"Response time {elapsed:.2f}s exceeds 2s threshold"


class TestLoadHandling:
    """Test system behavior under load"""

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_sustained_load(self, client, db_session, auth_token):
        """Test sustained load over time"""
        headers = {
            "Authorization": f"Bearer {auth_token}",
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
        }

        # Run requests for 30 seconds
        start_time = time.time()
        request_count = 0
        success_count = 0

        async def make_request():
            nonlocal request_count, success_count
            response = await client.get("/api/v1/documents/", headers=headers)
            request_count += 1
            if response.status_code == 200:
                success_count += 1

        tasks = []
        while time.time() - start_time < 10:  # 10 seconds for test
            tasks.append(asyncio.create_task(make_request()))
            await asyncio.sleep(0.1)  # 10 requests per second

        # Wait for all tasks
        await asyncio.gather(*tasks, return_exceptions=True)

        elapsed = time.time() - start_time
        rps = request_count / elapsed

        print(
            f"Sustained load: {request_count} requests in {elapsed:.1f}s ({rps:.1f} req/s)"
        )
        print(
            f"Success rate: {success_count}/{request_count} ({100*success_count/request_count:.1f}%)"
        )

        assert success_count / request_count > 0.95, "Success rate should be > 95%"

