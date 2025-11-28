"""
Admin Dashboard Endpoints
Provides statistics, charts, activity and metrics for admin panel

⚠️ TEMPORARY SOLUTION - MOCK DATA
See /docs/MVP_PLAN.md → "ТИМЧАСОВІ РІШЕННЯ" → #1
All endpoints return mock data (zeros/empty arrays) for MVP testing.
TODO: Replace with real database queries after generation pipeline is tested.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.dependencies import get_admin_user
from app.models.user import User
from app.models.document import Document, AIGenerationJob
from app.models.payment import Payment
from app.models.admin import AdminAuditLog

router = APIRouter()


@router.get("/stats")
async def get_admin_stats(
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get platform statistics for admin dashboard"""
    try:
        # Get today's date for filtering
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        
        # Count total users
        total_users_result = await db.execute(select(func.count(User.id)))
        total_users = total_users_result.scalar() or 0
        
        # Count active users today (users with last_login today or later)
        active_today_result = await db.execute(
            select(func.count(User.id)).where(User.last_login >= today)
        )
        active_users_today = active_today_result.scalar() or 0
        
        # Count total documents
        total_docs_result = await db.execute(select(func.count(Document.id)))
        total_documents = total_docs_result.scalar() or 0
        
        # Count completed documents
        completed_docs_result = await db.execute(
            select(func.count(Document.id)).where(Document.status == "completed")
        )
        completed_documents = completed_docs_result.scalar() or 0
        
        # Count active jobs (generating status)
        active_jobs_result = await db.execute(
            select(func.count(AIGenerationJob.id)).where(AIGenerationJob.status == "running")
        )
        active_jobs = active_jobs_result.scalar() or 0
        
        # Payment stats (will be 0 for now since we're not using payments in MVP)
        total_revenue = 0.0
        revenue_today = 0.0
        pending_refunds = 0
        
        return {
            "total_users": total_users,
            "active_users_today": active_users_today,
            "total_documents": total_documents,
            "completed_documents": completed_documents,
            "total_revenue": total_revenue,
            "revenue_today": revenue_today,
            "pending_refunds": pending_refunds,
            "active_jobs": active_jobs,
        }
    except Exception as e:
        # If anything fails, return zeros instead of crashing
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting admin stats: {e}", exc_info=True)
        return {
            "total_users": 0,
            "active_users_today": 0,
            "total_documents": 0,
            "completed_documents": 0,
            "total_revenue": 0.0,
            "revenue_today": 0.0,
            "pending_refunds": 0,
            "active_jobs": 0,
        }


@router.get("/dashboard/charts")
async def get_dashboard_charts(
    period: str = "week",
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get chart data for admin dashboard"""
    try:
        # Calculate period start
        now = datetime.utcnow()
        if period == "day":
            period_start = now - timedelta(days=1)
        elif period == "week":
            period_start = now - timedelta(days=7)
        elif period == "month":
            period_start = now - timedelta(days=30)
        else:
            period_start = now - timedelta(days=7)  # default to week
        
        # Get documents created in period (simple count for now)
        docs_result = await db.execute(
            select(func.count(Document.id)).where(Document.created_at >= period_start)
        )
        docs_count = docs_result.scalar() or 0
        
        # Get users created in period
        users_result = await db.execute(
            select(func.count(User.id)).where(User.created_at >= period_start)
        )
        users_count = users_result.scalar() or 0
        
        # Format as chart data arrays (frontend expects arrays)
        # Simple single-point data for MVP (can add daily breakdown later)
        today_str = now.date().isoformat()
        
        return {
            "period": period,
            "revenue": [{"date": today_str, "revenue": 0.0}],  # Array format
            "users": [{"date": today_str, "new_users": users_count}],  # Array format
            "documents": [{"date": today_str, "documents": docs_count}],  # Array format
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting dashboard charts: {e}", exc_info=True)
        today_str = datetime.utcnow().date().isoformat()
        return {
            "period": period,
            "revenue": [{"date": today_str, "revenue": 0.0}],
            "users": [{"date": today_str, "new_users": 0}],
            "documents": [{"date": today_str, "documents": 0}],
            "generated_at": datetime.utcnow().isoformat(),
        }


@router.get("/dashboard/activity")
async def get_dashboard_activity(
    activity_type: str = "recent",
    limit: int = 10,
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent activity for admin dashboard"""
    try:
        # Get recent audit logs
        logs_query = (
            select(AdminAuditLog)
            .order_by(AdminAuditLog.created_at.desc())
            .limit(limit)
        )
        logs_result = await db.execute(logs_query)
        logs = logs_result.scalars().all()
        
        # Format activities
        activities = []
        for log in logs:
            activities.append({
                "id": log.id,
                "action": log.action,
                "details": log.details or {},
                "user_id": log.user_id,
                "admin_id": log.admin_id,
                "ip_address": log.ip_address,
                "created_at": log.created_at.isoformat() if log.created_at else None,
            })
        
        return {
            "activity_type": activity_type,
            "activities": activities,
            "count": len(activities),
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting dashboard activity: {e}", exc_info=True)
        return {
            "activity_type": activity_type,
            "activities": [],
            "count": 0,
            "generated_at": datetime.utcnow().isoformat(),
        }


@router.get("/dashboard/metrics")
async def get_dashboard_metrics(
    current_admin: User = Depends(get_admin_user),
    db: AsyncSession = Depends(get_db),
):
    """Get business metrics for admin dashboard"""
    try:
        # Count active users (logged in within last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        active_users_result = await db.execute(
            select(func.count(User.id)).where(User.last_login >= thirty_days_ago)
        )
        total_active_users = active_users_result.scalar() or 0
        
        # Average document pages
        avg_pages_result = await db.execute(
            select(func.avg(Document.target_pages)).where(Document.status == "completed")
        )
        avg_doc_pages = avg_pages_result.scalar() or 0
        
        # Count documents by status
        total_docs_result = await db.execute(select(func.count(Document.id)))
        total_docs = total_docs_result.scalar() or 0
        
        completed_docs_result = await db.execute(
            select(func.count(Document.id)).where(Document.status == "completed")
        )
        completed_docs = completed_docs_result.scalar() or 0
        
        # Calculate completion rate
        completion_rate = (completed_docs / total_docs * 100) if total_docs > 0 else 0
        
        return {
            "total_active_users": total_active_users,
            "total_documents": total_docs,
            "completed_documents": completed_docs,
            "completion_rate": round(completion_rate, 2),
            "avg_document_pages": round(float(avg_doc_pages), 2) if avg_doc_pages else 0,
            "users_with_payments": 0,  # Not using payments in MVP
            "mrr": 0.0,
            "arpu": 0.0,
            "conversion_rate": 0.0,
            "churn_rate": 0.0,
            "refund_rate": 0.0,
            "generated_at": datetime.utcnow().isoformat(),
        }
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting dashboard metrics: {e}", exc_info=True)
        return {
            "total_active_users": 0,
            "total_documents": 0,
            "completed_documents": 0,
            "completion_rate": 0.0,
            "avg_document_pages": 0.0,
            "users_with_payments": 0,
            "mrr": 0.0,
            "arpu": 0.0,
            "conversion_rate": 0.0,
            "churn_rate": 0.0,
            "refund_rate": 0.0,
            "generated_at": datetime.utcnow().isoformat(),
        }
