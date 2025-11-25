"""
User management endpoints for GDPR compliance
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import NotFoundError, ValidationError
from app.middleware.rate_limit import rate_limit
from app.models.auth import User
from app.services.gdpr_service import GDPRService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/export-data")
@rate_limit("5/hour")  # Limit export requests
async def export_user_data(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export all user data for GDPR compliance"""
    try:
        gdpr_service = GDPRService(db)
        data = await gdpr_service.export_user_data(user_id=current_user.id)

        # Return JSON response with download headers
        return JSONResponse(
            content=data,
            headers={
                "Content-Disposition": f'attachment; filename="user_data_{current_user.id}.json"',
                "Content-Type": "application/json",
            },
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception(f"Failed to export data for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export user data",
        ) from e


@router.delete("/delete-account")
@rate_limit("1/hour")  # Very restrictive - this is irreversible
async def delete_account(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete user account (anonymize for GDPR compliance)"""
    try:
        gdpr_service = GDPRService(db)
        result = await gdpr_service.delete_user_account(user_id=current_user.id)

        logger.info(f"Account deleted for user {current_user.id}")

        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception as e:
        logger.exception(f"Failed to delete account for user {current_user.id}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete account",
        ) from e
