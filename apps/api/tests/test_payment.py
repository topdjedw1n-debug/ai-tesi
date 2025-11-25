"""
Payment service and API endpoint tests
"""
import os

import pytest
from httpx import AsyncClient

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_payment.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
# Stripe test keys (mock mode)
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_key_not_used")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_mock_secret_not_used")

from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.auth import User
from app.models.payment import Payment
from main import app  # noqa: E402


@pytest.fixture
async def client():
    """Create async test client"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        ac.headers.update({
            "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
            "X-Requested-With": "XMLHttpRequest",
        })
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
        email="test@payment.com",
        full_name="Test Payment User",
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_token(client, test_user):
    """Get auth token for test user"""
    # Create magic link and verify it
    from datetime import datetime, timedelta

    from app.models.auth import MagicLinkToken

    token = MagicLinkToken(
        token="test_magic_link_token_payment",
        email=test_user.email,
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )
    async with AsyncSessionLocal() as session:
        session.add(token)
        await session.commit()

    # Verify magic link (POST request)
    response = await client.post(
        "/api/v1/auth/verify-magic-link",
        json={"token": "test_magic_link_token_payment"}
    )
    assert response.status_code == 200
    data = response.json()
    return data["access_token"]


class TestPaymentModel:
    """Test Payment model"""

    @pytest.mark.asyncio
    async def test_payment_model_creation(self, db_session, test_user):
        """Test creating a payment record"""
        payment = Payment(
            user_id=test_user.id,
            stripe_payment_intent_id="pi_test_12345",
            amount=25.50,
            currency="EUR",
            status="pending"
        )
        db_session.add(payment)
        await db_session.commit()
        await db_session.refresh(payment)

        assert payment.id is not None
        assert payment.user_id == test_user.id
        assert payment.amount == 25.50
        assert payment.status == "pending"
        assert payment.stripe_payment_intent_id == "pi_test_12345"


class TestPaymentService:
    """Test PaymentService"""

    @pytest.mark.asyncio
    async def test_payment_service_without_stripe_key(self, db_session):
        """Test that service raises error when Stripe is not configured"""
        # Temporarily unset Stripe key
        import os

        from app.services.payment_service import PaymentService
        old_key = os.environ.get("STRIPE_SECRET_KEY")
        os.environ.pop("STRIPE_SECRET_KEY", None)

        # Reload settings
        from app.core.config import settings
        object.__setattr__(settings, "STRIPE_SECRET_KEY", None)

        service = PaymentService(db_session)

        with pytest.raises(ValueError, match="Stripe not configured"):
            await service.create_payment_intent(
                user_id=1,
                amount=25.00
            )

        # Restore key for other tests
        if old_key:
            os.environ["STRIPE_SECRET_KEY"] = old_key


class TestPaymentAPI:
    """Test Payment API endpoints"""

    @pytest.mark.asyncio
    async def test_get_payment_history_unauthenticated(self, client):
        """Test that unauthenticated requests fail"""
        response = await client.get("/api/v1/payment/history")
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_payment_history_authenticated(self, client, auth_token):
        """Test getting payment history"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = await client.get("/api/v1/payment/history", headers=headers)

        # Should return empty list (no payments yet)
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0

    @pytest.mark.asyncio
    async def test_create_payment_intent_unauthenticated(self, client):
        """Test that unauthenticated requests fail"""
        response = await client.post(
            "/api/v1/payment/create-intent",
            json={"amount": 25.00, "currency": "EUR"}
        )
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_get_payment_not_found(self, client, auth_token):
        """Test getting non-existent payment"""
        headers = {"Authorization": f"Bearer {auth_token}"}
        response = await client.get("/api/v1/payment/99999", headers=headers)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_webhook_missing_signature(self, client):
        """Test webhook without signature fails"""
        response = await client.post(
            "/api/v1/payment/webhook",
            json={"type": "payment_intent.succeeded", "data": {}}
        )
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_webhook_invalid_signature(self, client):
        """Test webhook with invalid signature fails"""
        headers = {"Stripe-Signature": "invalid_signature"}
        response = await client.post(
            "/api/v1/payment/webhook",
            headers=headers,
            json={"type": "payment_intent.succeeded", "data": {}}
        )
        assert response.status_code in [400, 500]  # Signature validation fails

