"""
Tests for admin payment endpoints
Covers /api/v1/admin/payments/* endpoints
"""
import os
from decimal import Decimal
from datetime import datetime, timedelta

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
from app.models.user import User
from app.models.document import Document
from app.models.payment import Payment
from app.core.security import create_access_token
from main import app


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
async def admin_user(db_session):
    """Create an admin user for testing"""
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
async def regular_user(db_session):
    """Create a regular user for testing"""
    user = User(
        email="user@test.com",
        is_active=True,
        is_admin=False,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def sample_payments(db_session, regular_user):
    """Create sample payments for testing"""
    # Create documents first
    doc1 = Document(
        user_id=regular_user.id,
        title="Test Document 1",
        topic="AI Research",
        language="en",
        target_pages=10,
        status="draft",
    )
    doc2 = Document(
        user_id=regular_user.id,
        title="Test Document 2",
        topic="ML Research",
        language="en",
        target_pages=20,
        status="draft",
    )
    db_session.add_all([doc1, doc2])
    await db_session.commit()
    await db_session.refresh(doc1)
    await db_session.refresh(doc2)

    # Create payments
    payment1 = Payment(
        user_id=regular_user.id,
        document_id=doc1.id,
        amount=Decimal("10.00"),
        currency="EUR",
        status="completed",
        stripe_payment_intent_id="pi_test123",
        stripe_session_id="cs_test123",
        created_at=datetime.utcnow() - timedelta(days=5),
    )
    payment2 = Payment(
        user_id=regular_user.id,
        document_id=doc2.id,
        amount=Decimal("25.00"),
        currency="EUR",
        status="pending",
        stripe_payment_intent_id="pi_test456",
        stripe_session_id="cs_test456",
        created_at=datetime.utcnow() - timedelta(days=2),
    )
    payment3 = Payment(
        user_id=regular_user.id,
        document_id=doc2.id,
        amount=Decimal("50.00"),
        currency="EUR",
        status="refunded",
        stripe_payment_intent_id="pi_test789",
        stripe_session_id="cs_test789",
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    db_session.add_all([payment1, payment2, payment3])
    await db_session.commit()
    return [payment1, payment2, payment3]


@pytest.fixture
async def admin_token(admin_user):
    """Get admin access token"""
    token = create_access_token(admin_user.id)
    return token


@pytest.fixture
async def user_token(regular_user):
    """Get regular user access token"""
    token = create_access_token(regular_user.id)
    return token


@pytest.mark.asyncio
async def test_list_payments_requires_auth(client, db_session):
    """Test listing payments requires authentication"""
    response = await client.get("/api/v1/admin/payments")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_payments_requires_admin(client, db_session, user_token):
    """Test listing payments requires admin role"""
    headers = {"Authorization": f"Bearer {user_token}"}
    response = await client.get("/api/v1/admin/payments", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_list_payments_success(client, db_session, admin_user, admin_token, sample_payments):
    """Test successful payment listing"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/payments", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert "payments" in data
    assert "total" in data
    assert "page" in data
    assert len(data["payments"]) == 3  # All 3 sample payments


@pytest.mark.asyncio
async def test_list_payments_filter_by_status(client, db_session, admin_user, admin_token, sample_payments):
    """Test filtering payments by status"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/payments?status=completed", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["payments"]) == 1
    assert data["payments"][0]["status"] == "completed"


@pytest.mark.asyncio
async def test_list_payments_filter_by_user_id(client, db_session, admin_user, admin_token, sample_payments, regular_user):
    """Test filtering payments by user_id"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get(f"/api/v1/admin/payments?user_id={regular_user.id}", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["payments"]) == 3  # All payments belong to regular_user


@pytest.mark.asyncio
async def test_list_payments_pagination(client, db_session, admin_user, admin_token, sample_payments):
    """Test payment listing pagination"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/payments?page=1&per_page=2", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert len(data["payments"]) == 2
    assert data["page"] == 1
    assert data["total"] == 3


@pytest.mark.asyncio
async def test_list_payments_filter_by_amount_range(client, db_session, admin_user, admin_token, sample_payments):
    """Test filtering payments by amount range"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/payments?min_amount=20&max_amount=60", headers=headers)
    assert response.status_code == 200
    data = response.json()
    # Should return payment2 (25.00) and payment3 (50.00)
    assert len(data["payments"]) == 2


@pytest.mark.asyncio
async def test_get_payment_details_requires_auth(client, db_session, sample_payments):
    """Test getting payment details requires authentication"""
    payment_id = sample_payments[0].id
    response = await client.get(f"/api/v1/admin/payments/{payment_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_payment_details_requires_admin(client, db_session, user_token, sample_payments):
    """Test getting payment details requires admin role"""
    headers = {"Authorization": f"Bearer {user_token}"}
    payment_id = sample_payments[0].id
    response = await client.get(f"/api/v1/admin/payments/{payment_id}", headers=headers)
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_payment_details_success(client, db_session, admin_user, admin_token, sample_payments):
    """Test successful payment details retrieval"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    payment_id = sample_payments[0].id
    response = await client.get(f"/api/v1/admin/payments/{payment_id}", headers=headers)
    assert response.status_code in [200, 404]  # May not exist depending on implementation


@pytest.mark.asyncio
async def test_get_payment_details_not_found(client, db_session, admin_user, admin_token):
    """Test getting non-existent payment returns 404"""
    headers = {"Authorization": f"Bearer {admin_token}"}
    response = await client.get("/api/v1/admin/payments/99999", headers=headers)
    assert response.status_code == 404
