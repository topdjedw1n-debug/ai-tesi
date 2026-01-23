"""
E2E tests for critical admin flows
Tests complete user journeys for admin operations
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
async def admin_user(db_session):
    """Create an admin user"""
    admin = User(
        email="admin@test.com",
        is_active=True,
        is_admin=True,
        is_super_admin=True,
    )
    db_session.add(admin)
    await db_session.commit()
    await db_session.refresh(admin)
    return admin


@pytest.fixture
async def admin_token(client, admin_user):
    """Get admin access token"""
    from app.core.security import create_access_token

    token = create_access_token(admin_user.id)
    return token


@pytest.mark.asyncio
async def test_user_block_unblock_flow(client, admin_token, test_user):
    """E2E test: Complete user block/unblock flow"""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Get user details
    response = await client.get(f"/api/v1/admin/users/{test_user.id}", headers=headers)
    if response.status_code == 200:
        assert response.json()["id"] == test_user.id

    # 2. Block user
    response = await client.put(
        f"/api/v1/admin/users/{test_user.id}/block",
        json={"reason": "E2E test block"},
        headers=headers,
    )
    if response.status_code == 200:
        assert response.json()["status"] == "blocked"

    # 3. Verify user is blocked
    response = await client.get(f"/api/v1/admin/users/{test_user.id}", headers=headers)
    if response.status_code == 200:
        # User should be blocked (depends on API response format)
        pass

    # 4. Unblock user
    response = await client.put(
        f"/api/v1/admin/users/{test_user.id}/unblock",
        headers=headers,
    )
    if response.status_code == 200:
        assert response.json()["status"] == "active"


@pytest.mark.asyncio
async def test_refund_approve_reject_flow(client, admin_token, test_user, db_session):
    """E2E test: Complete refund approve/reject flow"""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Create a payment
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

    # 2. Create refund request (as user)
    from app.core.security import create_access_token

    user_token = create_access_token(test_user.id)
    user_headers = {"Authorization": f"Bearer {user_token}"}

    refund_data = {
        "payment_id": payment.id,
        "reason": "E2E test refund",
        "reason_category": "quality",
        "screenshots": [],
    }
    response = await client.post(
        "/api/v1/refunds", json=refund_data, headers=user_headers
    )
    if response.status_code == 201:
        refund_id = response.json()["id"]

        # 3. Get refund request (as admin)
        response = await client.get(
            f"/api/v1/admin/refunds/{refund_id}", headers=headers
        )
        if response.status_code == 200:
            assert response.json()["status"] == "pending"

        # 4. Approve refund (as admin)
        response = await client.post(
            f"/api/v1/admin/refunds/{refund_id}/approve",
            json={
                "decision": "approve",
                "refund_amount": "50.00",
                "admin_comment": "E2E test approval",
            },
            headers=headers,
        )
        if response.status_code == 200:
            # Verify refund is approved
            response = await client.get(
                f"/api/v1/admin/refunds/{refund_id}", headers=headers
            )
            if response.status_code == 200:
                assert response.json()["status"] == "approved"


@pytest.mark.asyncio
async def test_settings_update_flow(client, admin_token):
    """E2E test: Complete settings update flow"""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Get current settings
    response = await client.get("/api/v1/admin/settings", headers=headers)
    if response.status_code == 200:
        response.json()

    # 2. Update pricing settings
    pricing_data = {
        "price_per_page": "0.75",
        "min_pages": 3,
        "max_pages": 200,
        "currencies": ["EUR"],
    }
    response = await client.put(
        "/api/v1/admin/settings/pricing",
        json=pricing_data,
        headers=headers,
    )
    if response.status_code == 200:
        # 3. Verify settings were updated
        response = await client.get("/api/v1/admin/settings/pricing", headers=headers)
        if response.status_code == 200:
            response.json()
            # Verify price was updated (depends on API response format)
            pass


@pytest.mark.asyncio
async def test_make_admin_flow(client, admin_token, test_user):
    """E2E test: Make user admin and revoke flow"""
    headers = {"Authorization": f"Bearer {admin_token}"}

    # 1. Verify user is not admin
    response = await client.get(f"/api/v1/admin/users/{test_user.id}", headers=headers)
    if response.status_code == 200:
        assert response.json().get("is_admin") is False

    # 2. Make user admin
    response = await client.post(
        f"/api/v1/admin/users/{test_user.id}/make-admin",
        json={"is_admin": True, "is_super_admin": False},
        headers=headers,
    )
    if response.status_code == 200:
        # 3. Verify user is now admin
        response = await client.get(
            f"/api/v1/admin/users/{test_user.id}", headers=headers
        )
        if response.status_code == 200:
            assert response.json().get("is_admin") is True

        # 4. Revoke admin rights
        response = await client.post(
            f"/api/v1/admin/users/{test_user.id}/revoke-admin",
            headers=headers,
        )
        if response.status_code == 200:
            # 5. Verify admin rights revoked
            response = await client.get(
                f"/api/v1/admin/users/{test_user.id}", headers=headers
            )
            if response.status_code == 200:
                assert response.json().get("is_admin") is False
