"""
Unit tests for SettingsService
Tests settings service methods
"""
import os
from unittest.mock import AsyncMock, MagicMock

import pytest

# Set environment variables for tests
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault("JWT_SECRET", os.environ["SECRET_KEY"])
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")

from app.services.settings_service import SettingsService


@pytest.fixture
def mock_db():
    """Create a mock database session"""
    db = AsyncMock()
    return db


@pytest.fixture
def settings_service(mock_db):
    """Create SettingsService instance with mocked DB"""
    return SettingsService(mock_db)


@pytest.mark.asyncio
async def test_get_settings(settings_service, mock_db):
    """Test get_settings returns all settings grouped by category"""
    # Mock settings
    mock_settings = [
        MagicMock(category="pricing", key="pricing.price_per_page", value=0.5),
        MagicMock(category="pricing", key="pricing.min_pages", value=3),
        MagicMock(category="ai", key="ai.default_provider", value="openai"),
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_settings
    mock_db.execute.return_value = mock_result

    settings = await settings_service.get_settings()

    assert "pricing" in settings
    assert "ai" in settings
    assert settings["pricing"]["pricing.price_per_page"] == 0.5


@pytest.mark.asyncio
async def test_get_settings_by_category(settings_service, mock_db):
    """Test get_settings_by_category returns settings for category"""
    mock_settings = [
        MagicMock(key="pricing.price_per_page", value=0.5),
        MagicMock(key="pricing.min_pages", value=3),
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_settings
    mock_db.execute.return_value = mock_result

    settings = await settings_service.get_settings_by_category("pricing")

    assert "pricing.price_per_page" in settings
    assert settings["pricing.price_per_page"] == 0.5


@pytest.mark.asyncio
async def test_get_setting(settings_service, mock_db):
    """Test get_setting returns specific setting"""
    mock_setting = MagicMock()
    mock_setting.key = "pricing.price_per_page"
    mock_setting.value = 0.5

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_setting
    mock_db.execute.return_value = mock_result

    setting = await settings_service.get_setting("pricing.price_per_page")

    assert setting.key == "pricing.price_per_page"
    assert setting.value == 0.5


@pytest.mark.asyncio
async def test_update_setting_existing(settings_service, mock_db):
    """Test update_setting updates existing setting"""
    mock_setting = MagicMock()
    mock_setting.key = "pricing.price_per_page"
    mock_setting.value = 0.5
    mock_setting.version = 1

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_setting
    mock_db.execute.return_value = mock_result

    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()

    updated = await settings_service.update_setting(
        key="pricing.price_per_page",
        value=0.75,
        category="pricing",
        updated_by=1,
    )

    assert updated.version == 2  # Version incremented
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_setting_new(settings_service, mock_db):
    """Test update_setting creates new setting if doesn't exist"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()

    updated = await settings_service.update_setting(
        key="pricing.price_per_page",
        value=0.5,
        category="pricing",
        updated_by=1,
    )

    assert updated.version == 1  # New setting starts at version 1
    mock_db.add.assert_called_once()
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_update_settings(settings_service, mock_db):
    """Test update_settings updates multiple settings"""
    # Mock get_setting to return None for new settings
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()

    settings_dict = {
        "pricing.price_per_page": 0.5,
        "pricing.min_pages": 3,
    }

    updated = await settings_service.update_settings(
        category="pricing",
        settings=settings_dict,
        updated_by=1,
    )

    assert len(updated) == 2
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_get_pricing_settings(settings_service, mock_db):
    """Test get_pricing_settings returns pricing settings"""
    mock_settings = [
        MagicMock(key="pricing.price_per_page", value=0.5),
    ]

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = mock_settings
    mock_db.execute.return_value = mock_result

    settings = await settings_service.get_pricing_settings()

    assert "pricing.price_per_page" in settings


@pytest.mark.asyncio
async def test_update_pricing_settings(settings_service, mock_db):
    """Test update_pricing_settings updates pricing"""
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db.execute.return_value = mock_result

    mock_db.flush = AsyncMock()
    mock_db.refresh = AsyncMock()
    mock_db.commit = AsyncMock()

    settings_dict = {"pricing.price_per_page": 0.75}

    updated = await settings_service.update_pricing_settings(
        settings=settings_dict,
        updated_by=1,
    )

    assert len(updated) == 1
    mock_db.commit.assert_called_once()


@pytest.mark.asyncio
async def test_is_maintenance_enabled(settings_service, mock_db):
    """Test is_maintenance_enabled returns maintenance status"""
    # Test enabled
    mock_setting = MagicMock()
    mock_setting.value = True

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_setting
    mock_db.execute.return_value = mock_result

    is_enabled = await settings_service.is_maintenance_enabled()

    assert is_enabled is True

    # Test disabled
    mock_setting.value = False
    is_enabled = await settings_service.is_maintenance_enabled()

    assert is_enabled is False


@pytest.mark.asyncio
async def test_get_maintenance_allowed_ips(settings_service, mock_db):
    """Test get_maintenance_allowed_ips returns IP list"""
    mock_setting = MagicMock()
    mock_setting.value = ["192.168.1.1", "10.0.0.1"]

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_setting
    mock_db.execute.return_value = mock_result

    ips = await settings_service.get_maintenance_allowed_ips()

    assert len(ips) == 2
    assert "192.168.1.1" in ips


@pytest.mark.asyncio
async def test_get_maintenance_message(settings_service, mock_db):
    """Test get_maintenance_message returns message"""
    mock_setting = MagicMock()
    mock_setting.value = "Custom maintenance message"

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_setting
    mock_db.execute.return_value = mock_result

    message = await settings_service.get_maintenance_message()

    assert message == "Custom maintenance message"
