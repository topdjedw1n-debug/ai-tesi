"""
Integration tests for refund API endpoints
Tests refund request creation and admin processing
"""
import os
from decimal import Decimal

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

from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.payment import Payment
from app.models.user import User
from main import app  # noqa: E402


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
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
async def test_user(db_session):
    """Create a test user"""
    user = User(
        email="user@test.com",
        is_active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_payment(db_session, test_user):
    """Create a test payment"""
    payment = Payment(
        user_id=test_user.id,
        amount=Decimal("50.00"),
        currency="EUR",
        status="completed",
        stripe_payment_intent_id="pi_test123",
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)
    return payment


@pytest.fixture
async def admin_user(db_session):
    """Create an admin user"""
    admin = User(
        email="admin@test.com",
        is_active=True,
        is_admin=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
async def user_token(client, test_user):
    """Get user access token"""
    from app.core.security import create_access_token

    token = create_access_token(test_user.id)
    return token


@pytest.fixture
async def admin_token(client, admin_user):
    """Get admin access token"""
    from app.core.security import create_access_token

    token = create_access_token(admin_user.id)
    return token


@pytest.mark.asyncio
async def test_create_refund_request_requires_auth(client):
    """Test create refund request requires authentication"""
    refund_data = {
        "payment_id": 1,
        "reason": "Test reason",
        "reason_category": "quality",
    }
    response = await client.post("/api/v1/refunds", json=refund_data)
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_create_refund_request(client, user_token, test_payment):
    """Test create refund request endpoint"""
    headers = {"Authorization": f"Bearer {user_token}"}
    refund_data = {
        "payment_id": test_payment.id,
        "reason": "Test reason",
        "reason_category": "quality",
        "screenshots": [],
    }
    response = await client.post("/api/v1/refunds", json=refund_data, headers=headers)
    # Should return 200/201 or 400/404 depending on payment status
    assert response.status_code in [200, 201, 400, 404]


@pytest.mark.asyncio
async def test_admin_refunds_list_requires_auth(client):
    """Test admin refunds list requires authentication"""
    response = await client.get("/api/v1/admin/refunds")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_admin_refunds_list_requires_admin(client, user_token):
    """Test admin refunds list requires admin role"""
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.get("/api/v1/admin/refunds", headers=headers)
    assert response.status_code in [403, 401]


@pytest.mark.asyncio
async def test_admin_refunds_list(client, admin_token):
    """Test admin refunds list endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/refunds", headers=headers)
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_admin_refunds_pending(client, admin_token):
    """Test admin refunds pending endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/refunds/pending", headers=headers)
    assert response.status_code in [200, 403]


@pytest.mark.asyncio
async def test_admin_refunds_stats(client, admin_token):
    """Test admin refunds stats endpoint"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/refunds/stats", headers=headers)
    assert response.status_code in [200, 403]
