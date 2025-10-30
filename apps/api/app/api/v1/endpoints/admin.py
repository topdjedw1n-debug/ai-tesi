"""
Admin endpoints for monitoring and management
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional
from datetime import datetime, timedelta
from app.core.database import get_db
from app.services.admin_service import AdminService
from app.core.exceptions import AuthorizationError

router = APIRouter()


@router.get("/stats")
async def get_platform_stats(
    db: AsyncSession = Depends(get_db)
):
    """Get platform statistics"""
    try:
        # TODO: Add admin authentication
        admin_service = AdminService(db)
        result = await admin_service.get_platform_stats()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get platform statistics"
        )


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    """List all users (admin only)"""
    try:
        # TODO: Add admin authentication
        admin_service = AdminService(db)
        result = await admin_service.list_users(page, per_page, search)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list users"
        )


@router.get("/ai-jobs")
async def list_ai_jobs(
    page: int = Query(1, ge=1),
    per_page: int = Query(10, ge=1, le=100),
    user_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    db: AsyncSession = Depends(get_db)
):
    """List AI generation jobs (admin only)"""
    try:
        # TODO: Add admin authentication
        admin_service = AdminService(db)
        result = await admin_service.list_ai_jobs(
            page, per_page, user_id, start_date, end_date
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list AI jobs"
        )


@router.get("/costs")
async def get_cost_analysis(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    group_by: str = Query("day", regex="^(day|week|month)$"),
    db: AsyncSession = Depends(get_db)
):
    """Get cost analysis (admin only)"""
    try:
        # TODO: Add admin authentication
        admin_service = AdminService(db)
        result = await admin_service.get_cost_analysis(start_date, end_date, group_by)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get cost analysis"
        )


@router.get("/health")
async def health_check(
    db: AsyncSession = Depends(get_db)
):
    """Detailed health check for admin"""
    try:
        admin_service = AdminService(db)
        result = await admin_service.health_check()
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Health check failed"
        )
