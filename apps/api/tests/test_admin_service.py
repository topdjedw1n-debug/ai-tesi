"""
Unit tests for AdminService
Tests admin service methods without database dependencies (using mocks)
"""
import os
from datetime import datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from app.core.exceptions import NotFoundError
from app.services.admin_service import CRITICAL_ACTIONS, AdminService


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = AsyncMock()
    return db


@pytest.fixture
def admin_service(mock_db):
    """Create AdminService instance with mocked DB"""
    return AdminService(mock_db)


@pytest.mark.asyncio
async def test_get_platform_stats(admin_service, mock_db):
    """Test get_platform_stats returns correct statistics"""
    # Метод робить 11 викликів execute: user_count, active_users, doc_count,
    # completed_docs, total_jobs, tokens_from_jobs, tokens_from_docs,
    # avg_tokens, total_cost, recent_jobs, stuck_queued, stuck_running

    # Create separate mock results for each execute call
    def create_scalar_result(value):
        mock_result = MagicMock()
        mock_result.scalar.return_value = value
        return mock_result

    mock_db.execute.side_effect = [
        create_scalar_result(100),  # total_users
        create_scalar_result(50),  # active_users
        create_scalar_result(200),  # total_documents
        create_scalar_result(150),  # completed_documents
        create_scalar_result(500),  # total_ai_jobs
        create_scalar_result(1000000),  # total_tokens_from_jobs
        create_scalar_result(500000),  # total_tokens_from_docs
        create_scalar_result(5000),  # avg_tokens_per_doc
        create_scalar_result(10000),  # total_cost_cents
        create_scalar_result(10),  # recent_jobs
        create_scalar_result(2),  # stuck_queued
        create_scalar_result(1),  # stuck_running
    ]

    stats = await admin_service.get_platform_stats()

    # Check nested structure
    assert "users" in stats
    assert "documents" in stats
    assert "ai_usage" in stats
    assert "generated_at" in stats

    # Check user stats
    assert stats["users"]["total"] == 100
    assert stats["users"]["active_last_30_days"] == 50

    # Check document stats
    assert stats["documents"]["total"] == 200
    assert stats["documents"]["completed"] == 150


@pytest.mark.asyncio
async def test_block_user(admin_service, mock_db):
    """Test block_user updates user status"""
    # Mock user lookup
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.email = "test@example.com"
    mock_user.is_active = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock commit
    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    result = await admin_service.block_user(user_id=1, admin_id=2, reason="Test block")

    assert result["status"] == "blocked"
    assert mock_user.is_active is False
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_block_user_not_found(admin_service, mock_db):
    """Test block_user raises NotFoundError for non-existent user"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    with pytest.raises(NotFoundError):
        await admin_service.block_user(user_id=999, admin_id=1, reason="Test")


@pytest.mark.asyncio
async def test_unblock_user(admin_service, mock_db):
    """Test unblock_user updates user status"""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.email = "test@example.com"
    mock_user.is_active = False  # User is blocked

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    result = await admin_service.unblock_user(user_id=1, admin_id=2)

    assert result["status"] == "active"
    assert mock_user.is_active is True
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_user(admin_service, mock_db):
    """Test delete_user soft-deletes user"""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.is_active = True
    mock_user.is_super_admin = False  # Regular user, can be deleted

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    result = await admin_service.delete_user(user_id=1, admin_id=2)

    assert result["email"] == mock_user.email
    assert mock_user.is_active is False  # Soft deleted
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_make_admin(admin_service, mock_db):
    """Test make_admin grants admin privileges"""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.email = "user@example.com"
    mock_user.is_admin = False
    mock_user.is_super_admin = False

    # Mock admin user who is making the change (must be super_admin)
    mock_admin = MagicMock()
    mock_admin.id = 2
    mock_admin.is_super_admin = True

    # First call returns target user, second call returns admin user
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = mock_user
    mock_result_admin = MagicMock()
    mock_result_admin.scalar_one_or_none.return_value = mock_admin

    mock_db.execute.side_effect = [mock_result_user, mock_result_admin]

    mock_db.commit = AsyncMock()
    mock_db.refresh = AsyncMock()

    result = await admin_service.make_admin(
        user_id=1, admin_id=2, is_admin=True, is_super_admin=False
    )

    assert result["is_admin"] is True
    assert mock_user.is_admin is True
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_revoke_admin(admin_service, mock_db):
    """Test revoke_admin removes admin privileges"""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.is_admin = True
    mock_user.is_super_admin = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    mock_db.commit = AsyncMock()

    result = await admin_service.revoke_admin(user_id=1, admin_id=2)

    assert result["is_admin"] is False
    assert mock_user.is_admin is False
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_user_details(admin_service, mock_db):
    """Test get_user_details returns user information"""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.email = "test@example.com"
    mock_user.full_name = "Test User"
    mock_user.is_active = True
    mock_user.is_verified = True
    mock_user.is_admin = False
    mock_user.is_super_admin = False
    mock_user.preferred_language = "en"
    mock_user.timezone = "UTC"
    mock_user.total_tokens_used = 1000
    mock_user.total_documents_created = 5
    mock_user.total_cost = Decimal("50.00")
    mock_user.stripe_customer_id = "cus_test123"
    mock_user.created_at = datetime.utcnow()
    mock_user.updated_at = datetime.utcnow()
    mock_user.last_login = datetime.utcnow()

    # Mock first execute (get user)
    mock_user_result = MagicMock()
    mock_user_result.scalar_one_or_none.return_value = mock_user

    # Mock second execute (documents count)
    mock_doc_count_result = MagicMock()
    mock_doc_count_result.scalar.return_value = 5

    # Mock third execute (payments)
    mock_payments_result = MagicMock()
    mock_payments_result.first.return_value = (3, Decimal("100.00"), datetime.utcnow())

    # Mock fourth execute (last document date)
    mock_last_doc_result = MagicMock()
    mock_last_doc_result.scalar.return_value = datetime.utcnow()

    mock_db.execute.side_effect = [
        mock_user_result,
        mock_doc_count_result,
        mock_payments_result,
        mock_last_doc_result,
    ]

    result = await admin_service.get_user_details(user_id=1)

    assert result["id"] == 1
    assert result["email"] == "test@example.com"
    assert result["documents_count"] == 5
    assert result["payments_count"] == 3
    assert result["total_paid"] == Decimal("100.00")


@pytest.mark.asyncio
async def test_get_dashboard_charts(admin_service, mock_db):
    """Test get_dashboard_charts returns chart data"""
    # Mock database results for revenue, users, documents
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    charts = await admin_service.get_dashboard_charts(period="week")

    assert "revenue" in charts
    assert "users" in charts
    assert "documents" in charts
    assert charts["period"] == "week"


@pytest.mark.asyncio
async def test_get_dashboard_activity(admin_service, mock_db):
    """Test get_dashboard_activity returns activity items"""
    # Mock activity results
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    activity = await admin_service.get_dashboard_activity(
        activity_type="recent", limit=10
    )

    assert "activities" in activity
    assert "count" in activity
    assert activity["activity_type"] == "recent"


@pytest.mark.asyncio
async def test_get_dashboard_metrics(admin_service, mock_db):
    """Test get_dashboard_metrics returns business metrics"""
    # Mock database results - метод робить 9 викликів execute
    mock_result1 = MagicMock()
    mock_result1.scalar.return_value = Decimal("1000.00")  # MRR

    mock_result2 = MagicMock()
    mock_result2.scalar.return_value = 100  # total_active_users

    mock_result3 = MagicMock()
    mock_result3.scalar.return_value = 150  # total_users_all

    mock_result4 = MagicMock()
    mock_result4.scalar.return_value = 50  # users_with_payments

    mock_result5 = MagicMock()
    mock_result5.scalar.return_value = 5  # churned_users

    mock_result6 = MagicMock()
    mock_result6.scalar.return_value = 2  # total_refunds

    mock_result7 = MagicMock()
    mock_result7.scalar.return_value = 100  # total_payments

    mock_db.execute.side_effect = [
        mock_result1,
        mock_result2,
        mock_result3,
        mock_result4,
        mock_result5,
        mock_result6,
        mock_result7,
    ]

    metrics = await admin_service.get_dashboard_metrics()

    assert "mrr" in metrics
    assert "arpu" in metrics
    assert "conversion_rate" in metrics
    assert "churn_rate" in metrics
    assert "refund_rate" in metrics
    assert metrics["mrr"] == 1000.0
    assert metrics["total_active_users"] == 100


@pytest.mark.asyncio
async def test_send_email_to_user(admin_service, mock_db):
    """Test send_email_to_user sends email"""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.email = "test@example.com"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    mock_db.commit = AsyncMock()

    # Patch notification_service.send_email instead
    with patch(
        "app.services.notification_service.notification_service.send_email"
    ) as mock_send_email:
        mock_send_email.return_value = True

        result = await admin_service.send_email_to_user(
            user_id=1,
            subject="Test Subject",
            message="Test Message",
            admin_id=2,
        )

        assert result["sent"] is True
        assert result["email"] == "test@example.com"
        mock_send_email.assert_called_once()


@pytest.mark.asyncio
async def test_critical_actions_list():
    """Test CRITICAL_ACTIONS contains expected actions"""
    assert "delete_user" in CRITICAL_ACTIONS
    assert "change_pricing" in CRITICAL_ACTIONS
    assert "enable_maintenance" in CRITICAL_ACTIONS
    assert "approve_large_refund" in CRITICAL_ACTIONS
