"""
Stripe Webhook E2E Tests

E2E tests для повного webhook flow:
- Event handlers: payment_intent.succeeded, payment_failed, canceled
- Verify endpoint: payment verification after checkout
- IDOR protection: ownership checks
- Error handling: missing payments, unhandled events

Coverage target:
- payment_service.py: 36.89% → 50%+ (+13%)
- payment.py endpoint: 50.45% → 65%+ (+15%)

Created: 2025-12-03
"""
import json
import os
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
import stripe
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Set test environment
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_e2e_webhook")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_e2e_webhook")

from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.auth import MagicLinkToken, User
from app.models.document import Document
from app.models.payment import Payment
from app.services.payment_service import PaymentService
from main import app


# ========================================
# FIXTURES
# ========================================

@pytest.fixture
async def db_session():
    """Create isolated test database session"""
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        yield session

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    
    await engine.dispose()


@pytest.fixture
async def client():
    """Create async test client with CSRF bypass"""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        ac.headers.update({
            "X-CSRF-Token": "test-csrf-token-e2e-webhook",
            "X-Requested-With": "XMLHttpRequest",
        })
        yield ac


@pytest.fixture
async def test_user(db_session: AsyncSession):
    """Create test user"""
    user = User(
        email="webhook-e2e@test.com",
        full_name="Webhook E2E Test User",
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def other_user(db_session: AsyncSession):
    """Create another user for IDOR tests"""
    user = User(
        email="other-user@test.com",
        full_name="Other User",
        is_active=True,
        is_verified=True
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def test_document(db_session: AsyncSession, test_user: User):
    """Create test document"""
    doc = Document(
        user_id=test_user.id,
        title="E2E Webhook Test Document",
        topic="Testing Stripe webhook E2E flow",
        language="en",
        target_pages=10,
        status="draft"
    )
    db_session.add(doc)
    await db_session.commit()
    await db_session.refresh(doc)
    return doc


@pytest.fixture
async def auth_token(client: AsyncClient, test_user: User):
    """Get auth token for test user"""
    from datetime import datetime, timedelta
    
    token = MagicLinkToken(
        token="test_magic_link_webhook_e2e",
        email=test_user.email,
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )
    async with AsyncSessionLocal() as session:
        session.add(token)
        await session.commit()
    
    response = await client.post(
        "/api/v1/auth/verify-magic-link",
        json={"token": "test_magic_link_webhook_e2e"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
async def other_auth_token(client: AsyncClient, other_user: User):
    """Get auth token for other user"""
    from datetime import datetime, timedelta
    
    token = MagicLinkToken(
        token="test_magic_link_other_user",
        email=other_user.email,
        expires_at=datetime.utcnow() + timedelta(minutes=30)
    )
    async with AsyncSessionLocal() as session:
        session.add(token)
        await session.commit()
    
    response = await client.post(
        "/api/v1/auth/verify-magic-link",
        json={"token": "test_magic_link_other_user"}
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def webhook_event_factory():
    """Factory for creating Stripe webhook events"""
    def create_event(
        event_type: str,
        payment_intent_id: str,
        session_id: str | None = None,
        amount: int = 2500,
        **kwargs
    ):
        """Create webhook event dict"""
        event = {
            "id": f"evt_test_{payment_intent_id}",
            "type": event_type,
            "data": {
                "object": {
                    "id": payment_intent_id if "intent" in event_type else session_id,
                    "object": "payment_intent" if "intent" in event_type else "checkout.session",
                    "amount": amount,
                    "currency": "eur",
                    "status": "succeeded" if "succeeded" in event_type else "pending",
                    **kwargs
                }
            }
        }
        
        # Add session-specific fields
        if event_type == "checkout.session.completed" and session_id:
            event["data"]["object"]["payment_intent"] = payment_intent_id
            event["data"]["object"]["id"] = session_id
        
        # Add failure reason for failed events
        if "failed" in event_type:
            event["data"]["object"]["last_payment_error"] = {
                "message": "Card declined"
            }
        
        return event
    
    return create_event


@pytest.fixture
def mock_stripe():
    """Mock stripe webhook signature verification"""
    with patch('stripe.Webhook.construct_event') as mock_webhook:
        yield mock_webhook


# ========================================
# TEST 1: payment_intent.succeeded Handler
# ========================================

@pytest.mark.asyncio
async def test_webhook_payment_intent_succeeded_e2e(
    db_session: AsyncSession,
    test_user: User,
    test_document: Document,
    mock_stripe,
    webhook_event_factory
):
    """
    Test: payment_intent.succeeded event completes payment
    
    Coverage: payment_service.py lines 357-396 (_handle_payment_success)
    
    Expected:
    - Payment status: pending → completed
    - Document status: payment_pending → generating
    - Payment method saved
    """
    service = PaymentService(db_session)
    
    # Create payment in pending state
    payment = Payment(
        user_id=test_user.id,
        document_id=test_document.id,
        stripe_payment_intent_id="pi_test_succeeded_e2e",
        stripe_session_id="cs_test_succeeded",
        amount=Decimal("25.00"),
        currency="EUR",
        status="pending"
    )
    db_session.add(payment)
    
    # Set document status to payment_pending
    test_document.status = "payment_pending"
    
    await db_session.commit()
    await db_session.refresh(payment)
    
    # Create webhook event
    event = webhook_event_factory(
        "payment_intent.succeeded",
        "pi_test_succeeded_e2e",
        payment_method_types=["card"]
    )
    mock_stripe.return_value = event
    
    # Handle webhook
    payload = json.dumps(event).encode()
    signature = "test_signature_succeeded"
    
    result = await service.handle_webhook(payload, signature)
    
    # VERIFY: Payment completed
    assert result.status == "completed"
    assert result.completed_at is not None
    assert result.payment_method == "card"
    
    # VERIFY: Document status updated
    await db_session.refresh(test_document)
    assert test_document.status == "generating"
    
    print(f"✅ Test 1 PASSED: payment_intent.succeeded handled correctly")


# ========================================
# TEST 2: payment_intent.payment_failed Handler
# ========================================

@pytest.mark.asyncio
async def test_webhook_payment_intent_failed_e2e(
    db_session: AsyncSession,
    test_user: User,
    test_document: Document,
    mock_stripe,
    webhook_event_factory
):
    """
    Test: payment_intent.payment_failed event marks payment as failed
    
    Coverage: payment_service.py lines 400-428 (_handle_payment_failed)
    
    Expected:
    - Payment status: pending → failed
    - Failure reason saved
    - Document status: → payment_failed
    """
    service = PaymentService(db_session)
    
    # Create payment
    payment = Payment(
        user_id=test_user.id,
        document_id=test_document.id,
        stripe_payment_intent_id="pi_test_failed_e2e",
        amount=Decimal("25.00"),
        currency="EUR",
        status="pending"
    )
    db_session.add(payment)
    await db_session.commit()
    
    # Create webhook event
    event = webhook_event_factory(
        "payment_intent.payment_failed",
        "pi_test_failed_e2e"
    )
    mock_stripe.return_value = event
    
    # Handle webhook
    payload = json.dumps(event).encode()
    result = await service.handle_webhook(payload, "test_sig")
    
    # VERIFY: Payment failed
    assert result.status == "failed"
    assert result.failure_reason == "Card declined"
    
    # VERIFY: Document status updated
    await db_session.refresh(test_document)
    assert test_document.status == "payment_failed"
    
    print(f"✅ Test 2 PASSED: payment_intent.payment_failed handled correctly")


# ========================================
# TEST 3: payment_intent.canceled Handler
# ========================================

@pytest.mark.asyncio
async def test_webhook_payment_intent_canceled_e2e(
    db_session: AsyncSession,
    test_user: User,
    mock_stripe,
    webhook_event_factory
):
    """
    Test: payment_intent.canceled event marks payment as canceled
    
    Coverage: payment_service.py lines 432-446 (_handle_payment_canceled)
    
    Expected:
    - Payment status: pending → canceled
    """
    service = PaymentService(db_session)
    
    # Create payment
    payment = Payment(
        user_id=test_user.id,
        stripe_payment_intent_id="pi_test_canceled_e2e",
        amount=Decimal("25.00"),
        currency="EUR",
        status="pending"
    )
    db_session.add(payment)
    await db_session.commit()
    
    # Create webhook event
    event = webhook_event_factory(
        "payment_intent.canceled",
        "pi_test_canceled_e2e"
    )
    mock_stripe.return_value = event
    
    # Handle webhook
    payload = json.dumps(event).encode()
    result = await service.handle_webhook(payload, "test_sig")
    
    # VERIFY: Payment canceled
    assert result.status == "canceled"
    
    print(f"✅ Test 3 PASSED: payment_intent.canceled handled correctly")


# ========================================
# TEST 4: Unhandled Event Type
# ========================================

@pytest.mark.asyncio
async def test_webhook_unhandled_event_logged(
    db_session: AsyncSession,
    mock_stripe
):
    """
    Test: Unhandled event types logged and return None
    
    Coverage: payment_service.py lines 298-300 (else branch in handle_webhook)
    
    Expected:
    - Warning logged
    - Return None (no error)
    """
    service = PaymentService(db_session)
    
    # Create unhandled event
    event = {
        "id": "evt_test_unhandled",
        "type": "charge.refunded",  # Not handled
        "data": {"object": {"id": "ch_test_123"}}
    }
    mock_stripe.return_value = event
    
    # Handle webhook with logging mock
    with patch('app.services.payment_service.logger') as mock_logger:
        payload = json.dumps(event).encode()
        result = await service.handle_webhook(payload, "test_sig")
        
        # VERIFY: Return None
        assert result is None
        
        # VERIFY: Warning logged
        mock_logger.warning.assert_called()
        warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
        assert any("unhandled event" in call.lower() for call in warning_calls)
    
    print(f"✅ Test 4 PASSED: Unhandled event logged correctly")


# ========================================
# TEST 5: Verify Payment Endpoint Success
# ========================================

@pytest.mark.asyncio
async def test_verify_payment_endpoint_success(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    test_document: Document,
    auth_token: str
):
    """
    Test: /verify endpoint returns payment details after checkout
    
    Coverage: payment.py lines 182-231 (verify_payment endpoint)
    
    Expected:
    - 200 response
    - Payment details in response
    - Document ID returned
    """
    # Create completed payment
    payment = Payment(
        user_id=test_user.id,
        document_id=test_document.id,
        stripe_session_id="cs_test_verify_e2e",
        stripe_payment_intent_id="pi_test_verify",
        amount=Decimal("25.00"),
        currency="EUR",
        status="completed"
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)
    
    # Call verify endpoint
    response = await client.get(
        f"/api/v1/payment/verify?session_id=cs_test_verify_e2e",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # VERIFY: Success response
    assert response.status_code == 200
    data = response.json()
    
    assert data["success"] is True
    assert data["status"] == "completed"
    assert data["payment_id"] == payment.id
    assert data["document_id"] == test_document.id
    assert float(data["amount"]) == 25.00
    assert data["currency"] == "EUR"
    
    print(f"✅ Test 5 PASSED: Verify payment endpoint works correctly")


# ========================================
# TEST 6: Verify Payment Not Found
# ========================================

@pytest.mark.asyncio
async def test_verify_payment_not_found(
    client: AsyncClient,
    auth_token: str
):
    """
    Test: /verify endpoint returns 404 for non-existent session
    
    Coverage: payment.py error branch (lines 207-208)
    
    Expected:
    - 404 error
    - "Payment not found" message
    """
    response = await client.get(
        "/api/v1/payment/verify?session_id=cs_nonexistent",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    
    # VERIFY: 404 error
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
    
    print(f"✅ Test 6 PASSED: Verify payment not found returns 404")


# ========================================
# TEST 7: Verify Payment IDOR Protection
# ========================================

@pytest.mark.asyncio
async def test_verify_payment_ownership_check(
    client: AsyncClient,
    db_session: AsyncSession,
    test_user: User,
    other_user: User,
    other_auth_token: str
):
    """
    Test: /verify endpoint blocks access to other user's payment
    
    Coverage: payment.py IDOR check (lines 210-211)
    
    Expected:
    - User A creates payment
    - User B cannot access it
    - 404 error (not 403 to hide existence)
    """
    # Create payment for test_user
    payment = Payment(
        user_id=test_user.id,
        stripe_session_id="cs_test_idor_e2e",
        amount=Decimal("25.00"),
        currency="EUR",
        status="completed"
    )
    db_session.add(payment)
    await db_session.commit()
    
    # Try to access as other_user
    response = await client.get(
        "/api/v1/payment/verify?session_id=cs_test_idor_e2e",
        headers={"Authorization": f"Bearer {other_auth_token}"}
    )
    
    # VERIFY: 404 error (not 403)
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()
    
    print(f"✅ Test 7 PASSED: IDOR protection works (404 for other user)")


# ========================================
# TEST 8: Webhook Payment Not Found Error
# ========================================

@pytest.mark.asyncio
async def test_webhook_payment_not_found_error(
    db_session: AsyncSession,
    mock_stripe,
    webhook_event_factory
):
    """
    Test: Webhook with non-existent payment raises ValueError
    
    Coverage: payment_service.py error handling (lines 373-374, 407-408)
    
    Expected:
    - ValueError raised with "Payment not found" message
    """
    service = PaymentService(db_session)
    
    # Create event for non-existent payment
    event = webhook_event_factory(
        "payment_intent.succeeded",
        "pi_nonexistent_payment"
    )
    mock_stripe.return_value = event
    
    # Handle webhook - should raise ValueError
    payload = json.dumps(event).encode()
    
    with pytest.raises(ValueError, match="Payment not found"):
        await service.handle_webhook(payload, "test_sig")
    
    print(f"✅ Test 8 PASSED: Missing payment raises ValueError")


# ========================================
# TEST SUMMARY
# ========================================

@pytest.mark.asyncio
async def test_summary():
    """
    Test Suite Summary for Stripe Webhook E2E
    
    Tests created: 8
    Coverage targets:
    - payment_service.py: 36.89% → 50%+ (event handlers)
    - payment.py endpoint: 50.45% → 65%+ (verify endpoint, IDOR)
    
    Test breakdown:
    1. ✅ payment_intent.succeeded handler
    2. ✅ payment_intent.payment_failed handler
    3. ✅ payment_intent.canceled handler
    4. ✅ Unhandled event type logging
    5. ✅ Verify payment endpoint success
    6. ✅ Verify payment not found (404)
    7. ✅ Verify payment IDOR protection
    8. ✅ Webhook payment not found error
    
    All tests use:
    - Real AsyncSession (test DB)
    - Mocked Stripe SDK (stripe.Webhook.construct_event)
    - E2E flow (endpoint → service → database)
    """
    print("\n" + "="*60)
    print("✅ STRIPE WEBHOOK E2E TEST SUITE")
    print("="*60)
    print("Tests: 8 created")
    print("Target coverage: payment_service 50%+, payment endpoint 65%+")
    print("="*60)
