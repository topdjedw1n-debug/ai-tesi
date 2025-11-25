"""
Unit tests for RefundService
Tests refund service methods
"""
import os
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from app.services.refund_service import RefundService


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = AsyncMock()
    return db


@pytest.fixture
def refund_service(mock_db):
    """Create RefundService instance with mocked DB"""
    return RefundService(mock_db)


@pytest.mark.asyncio
async def test_create_refund_request(refund_service, mock_db):
    """Test create_refund_request creates refund request successfully"""
    # Mock payment lookup
    mock_payment = MagicMock()
    mock_payment.id = 1
    mock_payment.user_id = 1
    mock_payment.status = "completed"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_payment
    mock_db.execute.return_value = mock_result

    # Mock existing refund check (no existing refund)
    mock_existing_result = MagicMock()
    mock_existing_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_existing_result

    # Mock commit
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    refund_request = await refund_service.create_refund_request(
        user_id=1,
        payment_id=1,
        reason="Test reason",
        reason_category="quality",
        screenshots=["http://example.com/screenshot.png"],
    )

    assert refund_request.status == "pending"
    assert refund_request.payment_id == 1
    assert refund_request.user_id == 1
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_create_refund_request_payment_not_found(refund_service, mock_db):
    """Test create_refund_request raises error for non-existent payment"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="Payment not found"):
        await refund_service.create_refund_request(
            user_id=1,
            payment_id=999,
            reason="Test reason",
            reason_category="quality",
        )


@pytest.mark.asyncio
async def test_create_refund_request_payment_not_completed(refund_service, mock_db):
    """Test create_refund_request raises error for non-completed payment"""
    mock_payment = MagicMock()
    mock_payment.id = 1
    mock_payment.user_id = 1
    mock_payment.status = "pending"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_payment
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="Can only refund completed payments"):
        await refund_service.create_refund_request(
            user_id=1,
            payment_id=1,
            reason="Test reason",
            reason_category="quality",
        )


@pytest.mark.asyncio
async def test_get_refund_request(refund_service, mock_db):
    """Test get_refund_request returns refund request"""
    mock_refund = MagicMock()
    mock_refund.id = 1
    mock_refund.status = "pending"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_refund
    mock_db.execute.return_value = mock_result

    refund_request = await refund_service.get_refund_request(refund_id=1)

    assert refund_request.id == 1


@pytest.mark.asyncio
async def test_get_refund_request_not_found(refund_service, mock_db):
    """Test get_refund_request raises error for non-existent refund"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(ValueError, match="Refund request not found"):
        await refund_service.get_refund_request(refund_id=999)


@pytest.mark.asyncio
async def test_get_refunds_list(refund_service, mock_db):
    """Test get_refunds_list returns paginated refunds"""
    # Mock count query
    mock_count_result = MagicMock()
    mock_count_result.scalar.return_value = 10
    mock_db.execute.return_value = mock_count_result

    # Mock refunds query
    mock_refunds = [MagicMock(id=i, status="pending") for i in range(5)]
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_refunds
    mock_db.execute.return_value = mock_result

    result = await refund_service.get_refunds_list(
        status="pending",
        page=1,
        per_page=20,
    )

    assert "refunds" in result
    assert "total" in result
    assert result["total"] == 10
    assert result["page"] == 1
    assert result["per_page"] == 20


@pytest.mark.asyncio
@patch("app.services.refund_service.stripe")
async def test_approve_refund(mock_stripe, refund_service, mock_db):
    """Test approve_refund processes refund through Stripe"""
    # Mock refund request
    mock_refund = MagicMock()
    mock_refund.id = 1
    mock_refund.status = "pending"
    mock_refund.payment_id = 1
    mock_refund.user_id = 1

    mock_payment = MagicMock()
    mock_payment.id = 1
    mock_payment.stripe_payment_intent_id = "pi_test123"
    mock_payment.amount = Decimal("50.00")
    mock_payment.status = "completed"

    mock_refund.payment = mock_payment

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_refund
    mock_db.execute.return_value = mock_result

    # Mock Stripe refund
    mock_stripe.Refund.create.return_value = MagicMock(
        id="ref_test123", status="succeeded"
    )

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    refund_request = await refund_service.approve_refund(
        refund_id=1,
        admin_id=2,
        admin_comment="Approved",
        refund_amount=Decimal("50.00"),
    )

    assert refund_request.status == "approved"
    mock_stripe.Refund.create.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_reject_refund(refund_service, mock_db):
    """Test reject_refund updates refund status"""
    mock_refund = MagicMock()
    mock_refund.id = 1
    mock_refund.status = "pending"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_refund
    mock_db.execute.return_value = mock_result

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    refund_request = await refund_service.reject_refund(
        refund_id=1,
        admin_id=2,
        admin_comment="Rejected",
    )

    assert refund_request.status == "rejected"
    assert refund_request.admin_comment == "Rejected"
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_refund_stats(refund_service, mock_db):
    """Test get_refund_stats returns statistics"""
    # Mock database results
    mock_result = MagicMock()
    mock_result.scalar.side_effect = [
        100,  # total_requests
        20,  # pending
        60,  # approved
        20,  # rejected
        Decimal("5000.00"),  # total_refunded_amount
    ]
    mock_db.execute.return_value = mock_result

    # Mock average processing time
    mock_avg_result = MagicMock()
    mock_avg_result.scalar.return_value = 24.5  # hours
    mock_db.execute.return_value = mock_avg_result

    stats = await refund_service.get_refund_stats()

    assert "total_requests" in stats
    assert "pending" in stats
    assert "approved" in stats
    assert "rejected" in stats
    assert "total_refunded_amount" in stats
    assert stats["total_requests"] == 100
