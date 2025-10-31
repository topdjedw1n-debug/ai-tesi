"""
from typing import Dict, Any, Optional, List
Admin service for platform monitoring and management
"""

from datetime import datetime, timedelta
from typing import Any, Dict, Optional, List

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import AIGenerationJob, Document
from app.models.user import User

logger = structlog.get_logger()


class AdminService:
    """Service for admin operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_platform_stats(self) -> Dict[str, Any]:
        """Get platform statistics"""
        try:
            # Get user statistics
            user_count_result = await self.db.execute(select(func.count(User.id)))
            total_users = user_count_result.scalar()

            active_users_result = await self.db.execute(
                select(func.count(User.id)).where(
                    and_(
                        User.is_active is True,
                        User.last_login > datetime.utcnow() - timedelta(days=30)
                    )
                )
            )
            active_users = active_users_result.scalar()

            # Get document statistics
            doc_count_result = await self.db.execute(select(func.count(Document.id)))
            total_documents = doc_count_result.scalar()

            completed_docs_result = await self.db.execute(
                select(func.count(Document.id)).where(Document.status == "completed")
            )
            completed_documents = completed_docs_result.scalar()

            # Get AI usage statistics
            total_jobs_result = await self.db.execute(select(func.count(AIGenerationJob.id)))
            total_ai_jobs = total_jobs_result.scalar()

            total_tokens_result = await self.db.execute(
                select(func.sum(AIGenerationJob.total_tokens))
            )
            total_tokens = total_tokens_result.scalar() or 0

            total_cost_result = await self.db.execute(
                select(func.sum(AIGenerationJob.cost_cents))
            )
            total_cost_cents = total_cost_result.scalar() or 0

            # Get recent activity (last 24 hours)
            recent_jobs_result = await self.db.execute(
                select(func.count(AIGenerationJob.id)).where(
                    AIGenerationJob.started_at > datetime.utcnow() - timedelta(hours=24)
                )
            )
            recent_jobs = recent_jobs_result.scalar()

            return {
                "users": {
                    "total": total_users,
                    "active_last_30_days": active_users
                },
                "documents": {
                    "total": total_documents,
                    "completed": completed_documents
                },
                "ai_usage": {
                    "total_jobs": total_ai_jobs,
                    "total_tokens": total_tokens,
                    "total_cost_cents": total_cost_cents,
                    "recent_jobs_24h": recent_jobs
                },
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error("Failed to get platform stats", error=str(e))
            raise

    async def list_users(
        self,
        page: int = 1,
        per_page: int = 10,
        search: Optional[str] = None
    ) -> Dict[str, Any]:
        """List all users with pagination"""
        try:
            # Build query
            query = select(User)

            if search:
                query = query.where(User.email.ilike(f"%{search}%"))

            # Get total count
            count_query = select(func.count(User.id))
            if search:
                count_query = count_query.where(User.email.ilike(f"%{search}%"))

            total_result = await self.db.execute(count_query)
            total = total_result.scalar()

            # Get paginated results
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page).order_by(User.created_at.desc())

            result = await self.db.execute(query)
            users = result.scalars().all()

            # Convert to dict format
            user_list = []
            for user in users:
                user_list.append({
                    "id": user.id,
                    "email": user.email,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "created_at": user.created_at.isoformat(),
                    "last_login": user.last_login.isoformat() if user.last_login else None,
                    "total_tokens_used": user.total_tokens_used,
                    "total_cost": user.total_cost
                })

            return {
                "users": user_list,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            }

        except Exception as e:
            logger.error("Failed to list users", error=str(e))
            raise

    async def list_ai_jobs(
        self,
        page: int = 1,
        per_page: int = 10,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """List AI generation jobs with filters"""
        try:
            # Build query
            query = select(AIGenerationJob)

            if user_id:
                query = query.where(AIGenerationJob.user_id == user_id)

            if start_date:
                query = query.where(AIGenerationJob.started_at >= start_date)

            if end_date:
                query = query.where(AIGenerationJob.started_at <= end_date)

            # Get total count
            count_query = select(func.count(AIGenerationJob.id))
            if user_id:
                count_query = count_query.where(AIGenerationJob.user_id == user_id)
            if start_date:
                count_query = count_query.where(AIGenerationJob.started_at >= start_date)
            if end_date:
                count_query = count_query.where(AIGenerationJob.started_at <= end_date)

            total_result = await self.db.execute(count_query)
            total = total_result.scalar()

            # Get paginated results
            offset = (page - 1) * per_page
            query = query.offset(offset).limit(per_page).order_by(AIGenerationJob.started_at.desc())

            result = await self.db.execute(query)
            jobs = result.scalars().all()

            # Convert to dict format
            job_list = []
            for job in jobs:
                job_list.append({
                    "id": job.id,
                    "user_id": job.user_id,
                    "document_id": job.document_id,
                    "job_type": job.job_type,
                    "ai_provider": job.ai_provider,
                    "ai_model": job.ai_model,
                    "input_tokens": job.input_tokens,
                    "output_tokens": job.output_tokens,
                    "total_tokens": job.total_tokens,
                    "cost_cents": job.cost_cents,
                    "duration_ms": job.duration_ms,
                    "success": job.success,
                    "error_message": job.error_message,
                    "started_at": job.started_at.isoformat(),
                    "completed_at": job.completed_at.isoformat() if job.completed_at else None
                })

            return {
                "jobs": job_list,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page
            }

        except Exception as e:
            logger.error("Failed to list AI jobs", error=str(e))
            raise

    async def get_cost_analysis(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        group_by: str = "day"
    ) -> Dict[str, Any]:
        """Get cost analysis grouped by time period"""
        try:
            # Set default date range if not provided
            if not start_date:
                start_date = datetime.utcnow() - timedelta(days=30)
            if not end_date:
                end_date = datetime.utcnow()

            # TODO: Implement proper grouping based on group_by parameter
            # For now, return simple totals

            total_cost_result = await self.db.execute(
                select(func.sum(AIGenerationJob.cost_cents)).where(
                    and_(
                        AIGenerationJob.started_at >= start_date,
                        AIGenerationJob.started_at <= end_date
                    )
                )
            )
            total_cost = total_cost_result.scalar() or 0

            total_tokens_result = await self.db.execute(
                select(func.sum(AIGenerationJob.total_tokens)).where(
                    and_(
                        AIGenerationJob.started_at >= start_date,
                        AIGenerationJob.started_at <= end_date
                    )
                )
            )
            total_tokens = total_tokens_result.scalar() or 0

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "group_by": group_by
                },
                "totals": {
                    "total_cost_cents": total_cost,
                    "total_tokens": total_tokens,
                    "average_cost_per_token": total_cost / total_tokens if total_tokens > 0 else 0
                },
                "generated_at": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error("Failed to get cost analysis", error=str(e))
            raise

    async def health_check(self) -> Dict[str, Any]:
        """Detailed health check for admin"""
        try:
            # Check database connectivity
            db_result = await self.db.execute(select(1))
            db_healthy = db_result.scalar() == 1

            # Check recent AI job success rate
            recent_jobs_result = await self.db.execute(
                select(func.count(AIGenerationJob.id)).where(
                    AIGenerationJob.started_at > datetime.utcnow() - timedelta(hours=1)
                )
            )
            recent_jobs_count = recent_jobs_result.scalar()

            successful_jobs_result = await self.db.execute(
                select(func.count(AIGenerationJob.id)).where(
                    and_(
                        AIGenerationJob.started_at > datetime.utcnow() - timedelta(hours=1),
                        AIGenerationJob.success is True
                    )
                )
            )
            successful_jobs_count = successful_jobs_result.scalar()

            success_rate = successful_jobs_count / recent_jobs_count if recent_jobs_count > 0 else 1.0

            return {
                "status": "healthy" if db_healthy and success_rate > 0.8 else "degraded",
                "checks": {
                    "database": "healthy" if db_healthy else "unhealthy",
                    "ai_services": "healthy" if success_rate > 0.8 else "degraded"
                },
                "metrics": {
                    "recent_jobs_1h": recent_jobs_count,
                    "success_rate_1h": success_rate
                },
                "timestamp": datetime.utcnow().isoformat()
            }

        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat()
            }
