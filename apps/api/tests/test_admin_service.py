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
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
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
    # Mock database results
    mock_db.execute = AsyncMock()

    # Mock scalar results
    mock_result = MagicMock()
    mock_result.scalar.side_effect = [
        100,  # total_users
        50,  # active_users
        200,  # total_documents
        150,  # completed_documents
        500,  # total_ai_jobs
        1000000,  # total_tokens_from_jobs
        500000,  # total_tokens_from_docs
        5000,  # avg_tokens_per_doc
        10000,  # total_cost_cents
    ]

    mock_db.execute.return_value = mock_result

    # Mock recent activity
    mock_activity_result = MagicMock()
    mock_activity_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_activity_result

    stats = await admin_service.get_platform_stats()

    assert "total_users" in stats
    assert "active_users_today" in stats
    assert "total_documents" in stats
    assert "completed_documents" in stats
    assert "total_revenue" in stats


@pytest.mark.asyncio
async def test_block_user(admin_service, mock_db):
    """Test block_user updates user status"""
    # Mock user lookup
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.is_active = True
    mock_user.is_blocked = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock commit
    mock_db.commit = AsyncMock()

    result = await admin_service.block_user(user_id=1, admin_id=2, reason="Test block")

    assert result["status"] == "blocked"
    assert mock_user.is_blocked is True
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
    mock_user.is_active = True
    mock_user.is_blocked = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    mock_db.commit = AsyncMock()

    result = await admin_service.unblock_user(user_id=1, admin_id=2)

    assert result["status"] == "active"
    assert mock_user.is_blocked is False
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_delete_user(admin_service, mock_db):
    """Test delete_user soft-deletes user"""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.is_active = True
    mock_user.is_deleted = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    mock_db.commit = AsyncMock()

    result = await admin_service.delete_user(user_id=1, admin_id=2)

    assert result["status"] == "deleted"
    assert mock_user.is_deleted is True
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_make_admin(admin_service, mock_db):
    """Test make_admin grants admin privileges"""
    mock_user = MagicMock()
    mock_user.id = 1
    mock_user.is_admin = False
    mock_user.is_super_admin = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    mock_db.commit = AsyncMock()

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
    mock_user.registered_at = datetime.utcnow()
    mock_user.last_login = datetime.utcnow()
    mock_user.is_active = True
    mock_user.is_blocked = False
    mock_user.is_deleted = False
    mock_user.is_admin = False

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_user
    mock_db.execute.return_value = mock_result

    # Mock document count
    mock_doc_count = MagicMock()
    mock_doc_count.scalar.return_value = 5
    mock_db.execute.return_value = mock_doc_count

    # Mock payment sum
    mock_payment_sum = MagicMock()
    mock_payment_sum.scalar.return_value = Decimal("100.00")
    mock_db.execute.return_value = mock_payment_sum

    result = await admin_service.get_user_details(user_id=1)

    assert result["id"] == 1
    assert result["email"] == "test@example.com"
    assert "documents_count" in result
    assert "total_spent" in result


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
    # Mock database results
    mock_result = MagicMock()
    mock_result.scalar.side_effect = [
        1000.0,  # total_revenue
        100,  # total_users
        50,  # users_with_payments
        10,  # new_users_this_month
        5,  # churned_users
        2,  # refunds_count
    ]
    mock_db.execute.return_value = mock_result

    metrics = await admin_service.get_dashboard_metrics()

    assert "mrr" in metrics
    assert "arpu" in metrics
    assert "conversion_rate" in metrics
    assert "churn_rate" in metrics
    assert "refund_rate" in metrics


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

    with patch("app.services.admin_service.send_email") as mock_send_email:
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
