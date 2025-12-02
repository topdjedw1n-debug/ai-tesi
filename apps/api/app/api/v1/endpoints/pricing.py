"""
Pricing API endpoints for dynamic pricing
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_admin_user
from app.core.exceptions import APIException, ValidationError
from app.models.auth import User
from app.services.pricing_service import PricingService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/current")
async def get_current_price(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """
    Get current pricing configuration (public endpoint).

    No authentication required - used by frontend to display prices.
    """
    try:
        pricing_service = PricingService(db)
        config = await pricing_service.get_pricing_config()

        return {
            "price_per_page": config["price_per_page"],
            "min_pages": config["min_pages"],
            "max_pages": config["max_pages"],
            "currencies": config["currencies"],
        }
    except Exception as e:
        logger.error(f"Error getting current price: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get pricing configuration",
        ) from e


@router.get("/calculate")
async def calculate_price(
    request: Request,
    pages: int,
    db: AsyncSession = Depends(get_db),
):
    """
    Calculate total price for given number of pages (public endpoint).

    Args:
        pages: Number of pages

    Returns:
        dict: {
            "pages": int,
            "price_per_page": float,
            "total": float,
            "currency": str
        }
    """
    try:
        pricing_service = PricingService(db)

        # Validate pages
        is_valid, error_msg = await pricing_service.validate_pages(pages)
        if not is_valid:
            raise ValidationError(error_msg or "Invalid page count")

        # Calculate amount
        total = await pricing_service.calculate_amount(pages)
        config = await pricing_service.get_pricing_config()

        return {
            "pages": pages,
            "price_per_page": config["price_per_page"],
            "total": float(total),
            "currency": config["currencies"][0] if config["currencies"] else "EUR",
            "min_pages": config["min_pages"],
            "max_pages": config["max_pages"],
        }
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        ) from e
    except Exception as e:
        logger.error(f"Error calculating price: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to calculate price",
        ) from e


@router.get("/admin/current")
async def get_current_price_admin(
    request: Request,
    current_user: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Get current pricing configuration (admin endpoint).

    Same as public endpoint but requires admin authentication.
    Useful for admin dashboard.
    """
    try:
        pricing_service = PricingService(db)
        config = await pricing_service.get_pricing_config()

        return {
            "price_per_page": config["price_per_page"],
            "min_pages": config["min_pages"],
            "max_pages": config["max_pages"],
            "currencies": config["currencies"],
        }
    except Exception as e:
        logger.error(f"Error getting current price (admin): {e}", exc_info=True)
        raise APIException(
            detail="Failed to get pricing configuration",
            status_code=500,
            error_code="INTERNAL_SERVER_ERROR",
        ) from e

