"""
Settings service for managing system settings
"""

from datetime import datetime
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.admin import SystemSetting

logger = structlog.get_logger()


class SettingsService:
    """Service for managing system settings"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_settings(self) -> dict[str, Any]:
        """
        Get all settings grouped by category.

        Returns:
            dict: {category: {key: value, ...}, ...}
        """
        try:
            result = await self.db.execute(
                select(SystemSetting).order_by(
                    SystemSetting.category, SystemSetting.key
                )
            )
            settings = result.scalars().all()

            grouped: dict[str, dict[str, Any]] = {}
            for setting in settings:
                if str(setting.category) not in grouped:
                    grouped[str(setting.category)] = {}
                grouped[str(setting.category)][str(setting.key)] = setting.value

            return grouped
        except Exception as e:
            logger.error(f"Error getting all settings: {e}")
            raise

    async def get_settings_by_category(self, category: str) -> dict[str, Any]:
        """
        Get settings for a specific category.

        Args:
            category: Settings category (pricing, ai, limits, maintenance, etc.)

        Returns:
            dict: {key: value, ...}
        """
        try:
            result = await self.db.execute(
                select(SystemSetting)
                .where(SystemSetting.category == category)
                .order_by(SystemSetting.key)
            )
            settings = result.scalars().all()

            return {str(setting.key): setting.value for setting in settings}
        except Exception as e:
            logger.error(f"Error getting settings for category {category}: {e}")
            raise

    async def get_setting(self, key: str) -> SystemSetting | None:
        """
        Get a specific setting by key.

        Args:
            key: Setting key (e.g., "pricing.price_per_page")

        Returns:
            SystemSetting or None if not found
        """
        try:
            result = await self.db.execute(
                select(SystemSetting)
                .where(SystemSetting.key == key)
                .options(selectinload(SystemSetting.updater))
            )
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Error getting setting {key}: {e}")
            raise

    async def update_setting(
        self,
        key: str,
        value: Any,
        category: str,
        updated_by: int,
    ) -> SystemSetting:
        """
        Update a setting. Creates it if it doesn't exist.

        Args:
            key: Setting key
            value: New value (will be stored as JSON)
            category: Settings category
            updated_by: Admin user ID who is making the change

        Returns:
            Updated SystemSetting
        """
        try:
            # Check if setting exists
            existing = await self.get_setting(key)

            old_version = existing.version if existing else 0

            if existing:
                # Update existing setting
                await self.db.execute(
                    update(SystemSetting)
                    .where(SystemSetting.key == key)
                    .values(
                        value=value,
                        version=old_version + 1,
                        updated_by=updated_by,
                        updated_at=datetime.utcnow(),
                    )
                )
                await self.db.flush()
                await self.db.refresh(existing)
                logger.info(
                    f"Updated setting {key} from version {old_version} to {old_version + 1}"
                )
                return existing
            else:
                # Create new setting
                new_setting = SystemSetting(
                    key=key,
                    value=value,
                    category=category,
                    version=1,
                    updated_by=updated_by,
                    updated_at=datetime.utcnow(),
                )
                self.db.add(new_setting)
                await self.db.flush()
                await self.db.refresh(new_setting)
                logger.info(f"Created new setting {key}")
                return new_setting
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating setting {key}: {e}")
            raise

    async def update_settings(
        self,
        category: str,
        settings: dict[str, Any],
        updated_by: int,
    ) -> dict[str, SystemSetting]:
        """
        Update multiple settings in a category.

        Args:
            category: Settings category
            settings: Dict of {key: value} to update
            updated_by: Admin user ID who is making the change

        Returns:
            dict: {key: SystemSetting, ...} of updated settings
        """
        try:
            updated: dict[str, SystemSetting] = {}
            for key, value in settings.items():
                setting = await self.update_setting(key, value, category, updated_by)
                updated[key] = setting

            await self.db.commit()
            logger.info(f"Updated {len(updated)} settings in category {category}")
            return updated
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating settings in category {category}: {e}")
            raise

    async def get_setting_history(self, key: str) -> list[dict[str, Any]]:
        """
        Get history of changes for a setting.

        Note: This is a simplified version. In production, you might want
        to store a separate history table or use audit logs.

        Args:
            key: Setting key

        Returns:
            list: History entries with version, value, updated_by, updated_at
        """
        try:
            setting = await self.get_setting(key)
            if not setting:
                return []

            # For now, return current version. In production, you'd query
            # a history table or parse audit logs.
            return [
                {
                    "version": setting.version,
                    "value": setting.value,
                    "updated_by": setting.updated_by,
                    "updated_at": setting.updated_at.isoformat()
                    if setting.updated_at
                    else None,
                }
            ]
        except Exception as e:
            logger.error(f"Error getting history for setting {key}: {e}")
            raise

    # Convenience methods for specific setting categories

    async def get_pricing_settings(self) -> dict[str, Any]:
        """Get pricing settings"""
        return await self.get_settings_by_category("pricing")

    async def update_pricing_settings(
        self, settings: dict[str, Any], updated_by: int
    ) -> dict[str, SystemSetting]:
        """Update pricing settings"""
        return await self.update_settings("pricing", settings, updated_by)

    async def get_ai_settings(self) -> dict[str, Any]:
        """Get AI settings"""
        return await self.get_settings_by_category("ai")

    async def update_ai_settings(
        self, settings: dict[str, Any], updated_by: int
    ) -> dict[str, SystemSetting]:
        """Update AI settings"""
        return await self.update_settings("ai", settings, updated_by)

    async def get_limit_settings(self) -> dict[str, Any]:
        """Get limit settings"""
        return await self.get_settings_by_category("limits")

    async def update_limit_settings(
        self, settings: dict[str, Any], updated_by: int
    ) -> dict[str, SystemSetting]:
        """Update limit settings"""
        return await self.update_settings("limits", settings, updated_by)

    async def get_maintenance_settings(self) -> dict[str, Any]:
        """Get maintenance mode settings"""
        return await self.get_settings_by_category("maintenance")

    async def update_maintenance_settings(
        self, settings: dict[str, Any], updated_by: int
    ) -> dict[str, SystemSetting]:
        """Update maintenance mode settings"""
        return await self.update_settings("maintenance", settings, updated_by)

    async def is_maintenance_enabled(self) -> bool:
        """
        Check if maintenance mode is enabled.

        Returns:
            bool: True if maintenance mode is enabled
        """
        try:
            setting = await self.get_setting("maintenance.enabled")
            if setting:
                # setting.value is already the Python value, not Column
                return bool(setting.value) if setting.value is not None else False
            return False
        except Exception as e:
            logger.error(f"Error checking maintenance mode: {e}")
            return False

    async def get_maintenance_allowed_ips(self) -> list[str]:
        """
        Get list of IPs allowed during maintenance.

        Returns:
            list: List of IP addresses
        """
        try:
            setting = await self.get_setting("maintenance.allowed_ips")
            if setting and setting.value:
                value = setting.value
                if isinstance(value, list):
                    return value
                elif isinstance(value, str):
                    # Handle comma-separated string
                    return [ip.strip() for ip in value.split(",") if ip.strip()]
            return []
        except Exception as e:
            logger.error(f"Error getting maintenance allowed IPs: {e}")
            return []

    async def get_maintenance_message(self) -> str:
        """
        Get maintenance mode message.

        Returns:
            str: Maintenance message
        """
        try:
            setting = await self.get_setting("maintenance.message")
            if setting and setting.value:
                return str(setting.value)
            return "System maintenance in progress"
        except Exception as e:
            logger.error(f"Error getting maintenance message: {e}")
            return "System maintenance in progress"
