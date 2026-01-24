"""
Pricing service for dynamic price management
"""

from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ValidationError
from app.services.settings_service import SettingsService

logger = structlog.get_logger()


class PricingService:
    """Service for managing dynamic pricing"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings_service = SettingsService(db)

    async def get_current_price(self) -> Decimal:
        """
        Get current price per page from settings.

        Returns:
            Decimal: Price per page in EUR

        Raises:
            ValueError: If price cannot be retrieved
        """
        try:
            pricing_settings = await self.settings_service.get_pricing_settings()

            # Try different key formats
            price_value = None
            if "pricing.price_per_page" in pricing_settings:
                price_value = pricing_settings["pricing.price_per_page"]
            elif "price_per_page" in pricing_settings:
                price_value = pricing_settings["price_per_page"]

            if price_value is None:
                # Default price if not set
                logger.warning(
                    "Price per page not found in settings, using default €0.50"
                )
                return Decimal("0.50")

            # Convert to Decimal
            if isinstance(price_value, (int, float)):
                price = Decimal(str(price_value))
            elif isinstance(price_value, Decimal):
                price = price_value
            else:
                price = Decimal(str(price_value))

            if price <= 0:
                logger.warning("Invalid price from settings, using default €0.50")
                return Decimal("0.50")

            return price
        except Exception as e:
            logger.error(f"Error getting current price: {e}", exc_info=True)
            # Fallback to default price
            return Decimal("0.50")

    async def get_pricing_config(self) -> dict[str, Any]:
        """
        Get full pricing configuration.

        Returns:
            dict: {
                "price_per_page": Decimal,
                "min_pages": int,
                "max_pages": int,
                "currencies": list[str]
            }
        """
        try:
            pricing_settings = await self.settings_service.get_pricing_settings()

            # Extract values with fallback to defaults
            def get_value(key_with_prefix: str, key_simple: str, default: Any) -> Any:
                if key_with_prefix in pricing_settings:
                    return pricing_settings[key_with_prefix]
                elif key_simple in pricing_settings:
                    return pricing_settings[key_simple]
                return default

            price_per_page = get_value("pricing.price_per_page", "price_per_page", 0.50)
            min_pages = get_value("pricing.min_pages", "min_pages", 3)
            max_pages = get_value("pricing.max_pages", "max_pages", 200)
            currencies = get_value("pricing.currencies", "currencies", ["EUR"])

            # Ensure price is Decimal
            if not isinstance(price_per_page, Decimal):
                price_per_page = Decimal(str(price_per_page))

            return {
                "price_per_page": float(price_per_page),  # Convert to float for JSON
                "min_pages": int(min_pages),
                "max_pages": int(max_pages),
                "currencies": currencies
                if isinstance(currencies, list)
                else [str(currencies)],
            }
        except Exception as e:
            logger.error(f"Error getting pricing config: {e}", exc_info=True)
            # Return default configuration
            return {
                "price_per_page": 0.50,
                "min_pages": 3,
                "max_pages": 200,
                "currencies": ["EUR"],
            }

    async def calculate_amount(self, pages: int) -> Decimal:
        """
        Calculate total amount for given number of pages.

        Args:
            pages: Number of pages

        Returns:
            Decimal: Total amount in EUR

        Raises:
            ValidationError: If pages is invalid
        """
        if pages < 1:
            raise ValidationError("Pages must be at least 1")

        config = await self.get_pricing_config()
        min_pages = config["min_pages"]
        max_pages = config["max_pages"]

        if pages < min_pages:
            raise ValidationError(f"Minimum {min_pages} pages required")
        if pages > max_pages:
            raise ValidationError(f"Maximum {max_pages} pages allowed")

        price_per_page = Decimal(str(config["price_per_page"]))
        total = price_per_page * pages

        return total

    async def validate_pages(self, pages: int) -> tuple[bool, str | None]:
        """
        Validate number of pages against pricing limits.

        Args:
            pages: Number of pages to validate

        Returns:
            tuple: (is_valid, error_message)
        """
        try:
            config = await self.get_pricing_config()
            min_pages = config["min_pages"]
            max_pages = config["max_pages"]

            if pages < min_pages:
                return False, f"Minimum {min_pages} pages required"
            if pages > max_pages:
                return False, f"Maximum {max_pages} pages allowed"

            return True, None
        except Exception as e:
            logger.error(f"Error validating pages: {e}", exc_info=True)
            return False, "Error validating page count"
