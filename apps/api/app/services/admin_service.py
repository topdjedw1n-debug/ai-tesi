"""
Admin service for platform monitoring and management
"""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any

import structlog
from sqlalchemy import and_, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.core.logging import log_security_audit_event
from app.models.admin import AdminAuditLog
from app.models.document import AIGenerationJob, Document
from app.models.payment import Payment
from app.models.refund import RefundRequest
from app.models.user import User

logger = structlog.get_logger()

# Critical actions that require alerts
CRITICAL_ACTIONS = [
    "delete_user",
    "delete_all_user_data",
    "change_pricing",
    "enable_maintenance",
    "disable_2fa",
    "grant_super_admin",
    "approve_large_refund",  # > €100
]


class AdminService:
    """Service for admin operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_platform_stats(self) -> dict[str, Any]:
        """Get platform statistics"""
        try:
            # Get user statistics
            user_count_result = await self.db.execute(select(func.count(User.id)))
            total_users = user_count_result.scalar()

            active_users_result = await self.db.execute(
                select(func.count(User.id)).where(
                    and_(
                        User.is_active.is_(True),
                        User.last_login > datetime.utcnow() - timedelta(days=30),
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
            total_jobs_result = await self.db.execute(
                select(func.count(AIGenerationJob.id))
            )
            total_ai_jobs = total_jobs_result.scalar()

            # Tokens from AIGenerationJob
            total_tokens_from_jobs_result = await self.db.execute(
                select(func.sum(AIGenerationJob.total_tokens))
            )
            total_tokens_from_jobs = total_tokens_from_jobs_result.scalar() or 0

            # Tokens from Document.tokens_used
            total_tokens_from_docs_result = await self.db.execute(
                select(func.sum(Document.tokens_used))
            )
            total_tokens_from_docs = total_tokens_from_docs_result.scalar() or 0

            # Total tokens (combined from both sources)
            total_tokens = total_tokens_from_jobs + total_tokens_from_docs

            # Average tokens per document
            avg_tokens_per_doc_result = await self.db.execute(
                select(func.avg(Document.tokens_used)).where(Document.tokens_used > 0)
            )
            avg_tokens_per_doc = avg_tokens_per_doc_result.scalar() or 0

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

            # Check for stuck jobs (monitoring)
            stuck_threshold = datetime.utcnow() - timedelta(minutes=5)
            stuck_queued_result = await self.db.execute(
                select(func.count(AIGenerationJob.id)).where(
                    and_(
                        AIGenerationJob.status == "queued",
                        AIGenerationJob.started_at < stuck_threshold,
                        AIGenerationJob.completed_at.is_(None),
                    )
                )
            )
            stuck_queued = stuck_queued_result.scalar()

            stuck_running_threshold = datetime.utcnow() - timedelta(minutes=30)
            stuck_running_result = await self.db.execute(
                select(func.count(AIGenerationJob.id)).where(
                    and_(
                        AIGenerationJob.status == "running",
                        AIGenerationJob.started_at < stuck_running_threshold,
                        AIGenerationJob.completed_at.is_(None),
                    )
                )
            )
            stuck_running = stuck_running_result.scalar()

            # Return flat structure for frontend compatibility
            return {
                "total_users": total_users,
                "active_users_today": active_users,  # Actually last 30 days
                "total_documents": total_documents,
                "completed_documents": completed_documents,
                "total_revenue": 0.0,  # Not using payments in MVP
                "revenue_today": 0.0,
                "pending_refunds": 0,
                "active_jobs": recent_jobs,
            }

        except Exception as e:
            logger.error("Failed to get platform stats", error=str(e))
            raise

    async def list_users(
        self, page: int = 1, per_page: int = 10, search: str | None = None
    ) -> dict[str, Any]:
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
            query = (
                query.offset(offset).limit(per_page).order_by(User.created_at.desc())
            )

            result = await self.db.execute(query)
            users = result.scalars().all()

            # Convert to dict format
            user_list = []
            for user in users:
                user_list.append(
                    {
                        "id": user.id,
                        "email": user.email,
                        "is_active": user.is_active,
                        "is_verified": user.is_verified,
                        "created_at": user.created_at.isoformat(),
                        "last_login": user.last_login.isoformat()
                        if user.last_login
                        else None,
                        "total_tokens_used": user.total_tokens_used,
                        "total_cost": user.total_cost,
                    }
                )

            return {
                "users": user_list,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
            }

        except Exception as e:
            logger.error("Failed to list users", error=str(e))
            raise

    async def get_user_details(self, user_id: int) -> dict[str, Any]:
        """
        Get detailed user information with statistics.

        Args:
            user_id: User ID

        Returns:
            Dictionary with user details and statistics

        Raises:
            ValueError: If user not found
        """
        try:
            # Get user
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError("User not found")

            # Get documents count
            doc_count_result = await self.db.execute(
                select(func.count(Document.id)).where(Document.user_id == user_id)
            )
            documents_count = doc_count_result.scalar() or 0

            # Get payments count and total
            from app.models.payment import Payment

            payments_result = await self.db.execute(
                select(
                    func.count(Payment.id),
                    func.sum(Payment.amount),
                    func.max(Payment.completed_at),
                ).where(
                    and_(
                        Payment.user_id == user_id,
                        Payment.status == "completed",
                    )
                )
            )
            payments_row = payments_result.first()
            payments_count = payments_row[0] or 0
            total_paid = payments_row[1] or Decimal("0")
            last_payment_at = payments_row[2]

            # Get last document date
            last_doc_result = await self.db.execute(
                select(func.max(Document.created_at)).where(Document.user_id == user_id)
            )
            last_document_at = last_doc_result.scalar()

            return {
                "id": user.id,
                "email": user.email,
                "full_name": user.full_name,
                "is_active": user.is_active,
                "is_verified": user.is_verified,
                "is_admin": user.is_admin,
                "is_super_admin": user.is_super_admin,
                "preferred_language": user.preferred_language,
                "timezone": user.timezone,
                "total_tokens_used": user.total_tokens_used,
                "total_documents_created": user.total_documents_created,
                "total_cost": user.total_cost,
                "stripe_customer_id": user.stripe_customer_id,
                "created_at": user.created_at,
                "updated_at": user.updated_at,
                "last_login": user.last_login,
                "documents_count": documents_count,
                "payments_count": payments_count,
                "total_paid": total_paid,
                "last_payment_at": last_payment_at,
                "last_document_at": last_document_at,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get user details: {e}")
            raise ValueError(f"Failed to get user details: {str(e)}") from e

    async def block_user(
        self, user_id: int, reason: str, admin_id: int
    ) -> dict[str, Any]:
        """
        Block a user.

        Args:
            user_id: User ID to block
            reason: Reason for blocking
            admin_id: Admin user ID who is blocking

        Returns:
            Dictionary with updated user info

        Raises:
            NotFoundError: If user not found
            ValueError: If already blocked
        """
        try:
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise NotFoundError("User not found")

            if not user.is_active:
                raise ValueError("User is already blocked")

            # Block user
            user.is_active = False
            await self.db.commit()
            await self.db.refresh(user)

            logger.info(f"User {user_id} blocked by admin {admin_id}, reason: {reason}")

            return {
                "id": user.id,
                "email": user.email,
                "is_active": user.is_active,
                "status": "blocked",
                "blocked_at": datetime.utcnow().isoformat(),
                "reason": reason,
            }

        except (NotFoundError, ValueError):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to block user {user_id}: {e}")
            raise ValueError(f"Failed to block user: {str(e)}") from e

    async def unblock_user(self, user_id: int, admin_id: int) -> dict[str, Any]:
        """
        Unblock a user.

        Args:
            user_id: User ID to unblock
            admin_id: Admin user ID who is unblocking

        Returns:
            Dictionary with updated user info

        Raises:
            NotFoundError: If user not found
            ValueError: If already active
        """
        try:
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise NotFoundError("User not found")

            if user.is_active:
                raise ValueError("User is already active")

            # Unblock user
            user.is_active = True
            await self.db.commit()
            await self.db.refresh(user)

            logger.info(f"User {user_id} unblocked by admin {admin_id}")

            return {
                "id": user.id,
                "email": user.email,
                "is_active": user.is_active,
                "status": "active",
                "unblocked_at": datetime.utcnow().isoformat(),
            }

        except (NotFoundError, ValueError):
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to unblock user {user_id}: {e}")
            raise ValueError(f"Failed to unblock user: {str(e)}") from e

    async def delete_user(self, user_id: int, admin_id: int) -> dict[str, Any]:
        """
        Soft delete a user (mark as inactive and clear sensitive data).

        Args:
            user_id: User ID to delete
            admin_id: Admin user ID who is deleting

        Returns:
            Dictionary with deletion info

        Raises:
            ValueError: If user not found or cannot delete (e.g., super admin)
        """
        try:
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError("User not found")

            # Prevent deletion of super admin (optional safety check)
            if user.is_super_admin:
                raise ValueError("Cannot delete super admin")

            # Soft delete: mark as inactive
            user.is_active = False
            # Optionally clear sensitive data (email, etc.)
            # For GDPR compliance, you might want to anonymize instead of delete

            await self.db.commit()
            await self.db.refresh(user)

            logger.warning(f"User {user_id} soft-deleted by admin {admin_id}")

            return {
                "id": user.id,
                "email": user.email,
                "is_active": user.is_active,
                "deleted_at": datetime.utcnow().isoformat(),
            }

        except ValueError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to delete user {user_id}: {e}")
            raise ValueError(f"Failed to delete user: {str(e)}") from e

    async def make_admin(
        self,
        user_id: int,
        is_admin: bool,
        is_super_admin: bool | None,
        admin_id: int,
    ) -> dict[str, Any]:
        """
        Make user admin or revoke admin rights.

        Args:
            user_id: User ID to modify
            is_admin: True to make admin, False to revoke
            is_super_admin: True to make super admin (optional, requires super admin permission)
            admin_id: Admin user ID who is making the change

        Returns:
            Dictionary with updated user info

        Raises:
            ValueError: If user not found or invalid operation
        """
        try:
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError("User not found")

            # Update admin status
            user.is_admin = is_admin
            if is_super_admin is not None:
                # Only super admins can grant super admin status
                admin_user_result = await self.db.execute(
                    select(User).where(User.id == admin_id)
                )
                admin_user = admin_user_result.scalar_one_or_none()
                if admin_user and admin_user.is_super_admin:
                    user.is_super_admin = is_super_admin
                else:
                    raise ValueError("Only super admin can grant super admin status")

            # Revoke super admin if removing admin status
            if not is_admin:
                user.is_super_admin = False

            await self.db.commit()
            await self.db.refresh(user)

            logger.info(
                f"User {user_id} admin status updated by admin {admin_id}: "
                f"is_admin={is_admin}, is_super_admin={user.is_super_admin}"
            )

            return {
                "id": user.id,
                "email": user.email,
                "is_admin": user.is_admin,
                "is_super_admin": user.is_super_admin,
                "updated_at": datetime.utcnow().isoformat(),
            }

        except ValueError:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Failed to update admin status for user {user_id}: {e}")
            raise ValueError(f"Failed to update admin status: {str(e)}") from e

    async def revoke_admin(
        self,
        user_id: int,
        admin_id: int,
    ) -> dict[str, Any]:
        """
        Revoke admin rights from a user.

        Args:
            user_id: User ID to revoke admin rights from
            admin_id: Admin user ID who is making the change

        Returns:
            Dictionary with updated user info

        Raises:
            ValueError: If user not found
        """
        return await self.make_admin(
            user_id=user_id,
            is_admin=False,
            is_super_admin=None,
            admin_id=admin_id,
        )

    async def send_email_to_user(
        self,
        user_id: int,
        subject: str,
        message: str,
        admin_id: int,
    ) -> dict[str, Any]:
        """
        Send email to a user.

        Args:
            user_id: User ID to send email to
            subject: Email subject
            message: Email message (HTML or plain text)
            admin_id: Admin user ID who is sending the email

        Returns:
            Dictionary with result

        Raises:
            ValueError: If user not found
        """
        try:
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError("User not found")

            # Send email using notification service
            from app.services.notification_service import notification_service

            email_sent = await notification_service.send_email(
                to_email=user.email,
                subject=subject,
                html_body=message,
            )

            logger.info(
                f"Admin {admin_id} sent email to user {user_id} ({user.email}): "
                f"subject={subject}, sent={email_sent}"
            )

            return {
                "user_id": user_id,
                "email": user.email,
                "subject": subject,
                "sent": email_sent,
                "sent_at": datetime.utcnow().isoformat(),
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to send email to user {user_id}: {e}")
            raise ValueError(f"Failed to send email: {str(e)}") from e

    async def get_user_documents(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 10,
    ) -> dict[str, Any]:
        """
        Get documents for a specific user.

        Args:
            user_id: User ID
            page: Page number
            per_page: Items per page

        Returns:
            Dictionary with documents and pagination info
        """
        try:
            from app.models.document import Document

            # Verify user exists
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError("User not found")

            # Get total count
            count_result = await self.db.execute(
                select(func.count(Document.id)).where(Document.user_id == user_id)
            )
            total = count_result.scalar()

            # Get paginated documents
            offset = (page - 1) * per_page
            docs_result = await self.db.execute(
                select(Document)
                .where(Document.user_id == user_id)
                .offset(offset)
                .limit(per_page)
                .order_by(Document.created_at.desc())
            )
            documents = docs_result.scalars().all()

            # Convert to dict format
            doc_list = []
            for doc in documents:
                doc_list.append(
                    {
                        "id": doc.id,
                        "title": doc.title,
                        "topic": doc.topic,
                        "language": doc.language,
                        "status": doc.status,
                        "target_pages": doc.target_pages,
                        "actual_pages": doc.actual_pages,
                        "ai_provider": doc.ai_provider,
                        "ai_model": doc.ai_model,
                        "tokens_used": doc.tokens_used,
                        "created_at": doc.created_at.isoformat()
                        if doc.created_at
                        else None,
                        "completed_at": doc.completed_at.isoformat()
                        if doc.completed_at
                        else None,
                    }
                )

            return {
                "documents": doc_list,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get documents for user {user_id}: {e}")
            raise

    async def get_user_payments(
        self,
        user_id: int,
        page: int = 1,
        per_page: int = 10,
    ) -> dict[str, Any]:
        """
        Get payments for a specific user.

        Args:
            user_id: User ID
            page: Page number
            per_page: Items per page

        Returns:
            Dictionary with payments and pagination info
        """
        try:
            from app.models.payment import Payment

            # Verify user exists
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise ValueError("User not found")

            # Get total count
            count_result = await self.db.execute(
                select(func.count(Payment.id)).where(Payment.user_id == user_id)
            )
            total = count_result.scalar()

            # Get paginated payments
            offset = (page - 1) * per_page
            payments_result = await self.db.execute(
                select(Payment)
                .where(Payment.user_id == user_id)
                .offset(offset)
                .limit(per_page)
                .order_by(Payment.created_at.desc())
            )
            payments = payments_result.scalars().all()

            # Convert to dict format
            payment_list = []
            for payment in payments:
                payment_list.append(
                    {
                        "id": payment.id,
                        "document_id": payment.document_id,
                        "amount": float(payment.amount) if payment.amount else 0,
                        "currency": payment.currency,
                        "status": payment.status,
                        "stripe_payment_intent_id": payment.stripe_payment_intent_id,
                        "stripe_session_id": payment.stripe_session_id,
                        "discount_code": payment.discount_code,
                        "discount_amount": float(payment.discount_amount)
                        if payment.discount_amount
                        else 0,
                        "created_at": payment.created_at.isoformat()
                        if payment.created_at
                        else None,
                        "completed_at": payment.completed_at.isoformat()
                        if payment.completed_at
                        else None,
                    }
                )

            return {
                "payments": payment_list,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
            }

        except ValueError:
            raise
        except Exception as e:
            logger.error(f"Failed to get payments for user {user_id}: {e}")
            raise

    async def bulk_user_action(
        self,
        user_ids: list[int],
        action: str,
        admin_id: int,
        reason: str | None = None,
    ) -> dict[str, Any]:
        """
        Perform bulk action on users (block/unblock/delete).

        Args:
            user_ids: List of user IDs
            action: Action to perform (block, unblock, delete)
            admin_id: Admin user ID performing the action
            reason: Optional reason (for block action)

        Returns:
            Dictionary with results

        Raises:
            ValueError: If invalid action
        """
        if action not in ["block", "unblock", "delete"]:
            raise ValueError(f"Invalid action: {action}")

        successful = 0
        failed = 0
        errors = []

        for user_id in user_ids:
            try:
                if action == "block":
                    await self.block_user(user_id, reason or "Bulk block", admin_id)
                elif action == "unblock":
                    await self.unblock_user(user_id, admin_id)
                elif action == "delete":
                    await self.delete_user(user_id, admin_id)

                successful += 1
            except Exception as e:
                failed += 1
                errors.append({"user_id": user_id, "error": str(e)})

        logger.info(
            f"Bulk {action} action completed by admin {admin_id}: "
            f"successful={successful}, failed={failed}"
        )

        return {
            "action": action,
            "total_requested": len(user_ids),
            "successful": successful,
            "failed": failed,
            "errors": errors,
        }

    async def list_ai_jobs(
        self,
        page: int = 1,
        per_page: int = 10,
        user_id: int | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> dict[str, Any]:
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
                count_query = count_query.where(
                    AIGenerationJob.started_at >= start_date
                )
            if end_date:
                count_query = count_query.where(AIGenerationJob.started_at <= end_date)

            total_result = await self.db.execute(count_query)
            total = total_result.scalar()

            # Get paginated results
            offset = (page - 1) * per_page
            query = (
                query.offset(offset)
                .limit(per_page)
                .order_by(AIGenerationJob.started_at.desc())
            )

            result = await self.db.execute(query)
            jobs = result.scalars().all()

            # Convert to dict format
            job_list = []
            for job in jobs:
                job_list.append(
                    {
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
                        "completed_at": job.completed_at.isoformat()
                        if job.completed_at
                        else None,
                    }
                )

            return {
                "jobs": job_list,
                "total": total,
                "page": page,
                "per_page": per_page,
                "total_pages": (total + per_page - 1) // per_page,
            }

        except Exception as e:
            logger.error("Failed to list AI jobs", error=str(e))
            raise

    async def get_cost_analysis(
        self,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        group_by: str = "day",
    ) -> dict[str, Any]:
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
                        AIGenerationJob.started_at <= end_date,
                    )
                )
            )
            total_cost = total_cost_result.scalar() or 0

            total_tokens_result = await self.db.execute(
                select(func.sum(AIGenerationJob.total_tokens)).where(
                    and_(
                        AIGenerationJob.started_at >= start_date,
                        AIGenerationJob.started_at <= end_date,
                    )
                )
            )
            total_tokens = total_tokens_result.scalar() or 0

            return {
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                    "group_by": group_by,
                },
                "totals": {
                    "total_cost_cents": total_cost,
                    "total_tokens": total_tokens,
                    "average_cost_per_token": total_cost / total_tokens
                    if total_tokens > 0
                    else 0,
                },
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error("Failed to get cost analysis", error=str(e))
            raise

    async def health_check(self) -> dict[str, Any]:
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
                        AIGenerationJob.started_at
                        > datetime.utcnow() - timedelta(hours=1),
                        AIGenerationJob.success.is_(True),
                    )
                )
            )
            successful_jobs_count = successful_jobs_result.scalar()

            success_rate = (
                successful_jobs_count / recent_jobs_count
                if recent_jobs_count > 0
                else 1.0
            )

            return {
                "status": "healthy"
                if db_healthy and success_rate > 0.8
                else "degraded",
                "checks": {
                    "database": "healthy" if db_healthy else "unhealthy",
                    "ai_services": "healthy" if success_rate > 0.8 else "degraded",
                },
                "metrics": {
                    "recent_jobs_1h": recent_jobs_count,
                    "success_rate_1h": success_rate,
                },
                "timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error("Health check failed", error=str(e))
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }

    async def monitor_stuck_jobs(
        self, stuck_threshold_minutes: int = 5
    ) -> dict[str, Any]:
        """
        Monitor for stuck AI generation jobs

        Finds jobs that have been in 'queued' status for longer than threshold
        without any updates. This indicates jobs that were created but never
        started by the background task (possible race condition or error).

        Args:
            stuck_threshold_minutes: Minutes after which a 'queued' job is considered stuck

        Returns:
            dict with stuck_jobs count, jobs list, and recommendations
        """
        try:
            threshold_time = datetime.utcnow() - timedelta(
                minutes=stuck_threshold_minutes
            )

            # Find stuck jobs (queued status, older than threshold, not completed)
            stuck_jobs_result = await self.db.execute(
                select(AIGenerationJob)
                .where(
                    and_(
                        AIGenerationJob.status == "queued",
                        AIGenerationJob.started_at < threshold_time,
                        AIGenerationJob.completed_at.is_(None),
                    )
                )
                .order_by(AIGenerationJob.started_at.asc())
            )
            stuck_jobs = stuck_jobs_result.scalars().all()

            # Also find jobs stuck in 'running' status for too long (e.g., > 30 minutes)
            running_threshold_time = datetime.utcnow() - timedelta(minutes=30)
            stuck_running_result = await self.db.execute(
                select(AIGenerationJob)
                .where(
                    and_(
                        AIGenerationJob.status == "running",
                        AIGenerationJob.started_at < running_threshold_time,
                        AIGenerationJob.completed_at.is_(None),
                    )
                )
                .order_by(AIGenerationJob.started_at.asc())
            )
            stuck_running = stuck_running_result.scalars().all()

            # Convert to dict format
            stuck_jobs_list = []
            for job in stuck_jobs:
                stuck_jobs_list.append(
                    {
                        "id": job.id,
                        "user_id": job.user_id,
                        "document_id": job.document_id,
                        "job_type": job.job_type,
                        "status": job.status,
                        "started_at": job.started_at.isoformat(),
                        "stuck_for_minutes": int(
                            (datetime.utcnow() - job.started_at).total_seconds() / 60
                        ),
                    }
                )

            stuck_running_list = []
            for job in stuck_running:
                stuck_running_list.append(
                    {
                        "id": job.id,
                        "user_id": job.user_id,
                        "document_id": job.document_id,
                        "job_type": job.job_type,
                        "status": job.status,
                        "started_at": job.started_at.isoformat(),
                        "stuck_for_minutes": int(
                            (datetime.utcnow() - job.started_at).total_seconds() / 60
                        ),
                    }
                )

            total_stuck = len(stuck_jobs) + len(stuck_running)

            return {
                "stuck_jobs": {
                    "total": total_stuck,
                    "queued_stuck": len(stuck_jobs),
                    "running_stuck": len(stuck_running),
                },
                "queued_jobs": stuck_jobs_list,
                "running_jobs": stuck_running_list,
                "threshold_minutes": stuck_threshold_minutes,
                "monitored_at": datetime.utcnow().isoformat(),
                "recommendations": {
                    "cleanup_needed": total_stuck > 0,
                    "message": f"Found {total_stuck} stuck job(s). Consider running cleanup.",
                }
                if total_stuck > 0
                else {"cleanup_needed": False, "message": "No stuck jobs detected."},
            }

        except Exception as e:
            logger.error("Failed to monitor stuck jobs", error=str(e))
            raise

    async def cleanup_stuck_jobs(
        self, stuck_threshold_minutes: int = 5, action: str = "mark_failed"
    ) -> dict[str, Any]:
        """
        Cleanup stuck AI generation jobs

        Finds and handles jobs stuck in 'queued' or 'running' status.
        Actions:
        - 'mark_failed': Mark jobs as failed with error message
        - 'retry': Attempt to restart jobs (not implemented yet, would require job retry logic)

        Args:
            stuck_threshold_minutes: Minutes after which a job is considered stuck
            action: Action to take ('mark_failed' or 'retry')

        Returns:
            dict with cleanup results
        """
        try:
            threshold_time = datetime.utcnow() - timedelta(
                minutes=stuck_threshold_minutes
            )
            running_threshold_time = datetime.utcnow() - timedelta(minutes=30)

            cleaned_queued = 0
            cleaned_running = 0

            if action == "mark_failed":
                # Mark stuck queued jobs as failed
                queued_result = await self.db.execute(
                    update(AIGenerationJob)
                    .where(
                        and_(
                            AIGenerationJob.status == "queued",
                            AIGenerationJob.started_at < threshold_time,
                            AIGenerationJob.completed_at.is_(None),
                        )
                    )
                    .values(
                        status="failed",
                        success=False,
                        error_message=f"Job stuck in queued status for > {stuck_threshold_minutes} minutes. Automatically cleaned up.",
                        completed_at=datetime.utcnow(),
                    )
                )
                cleaned_queued = queued_result.rowcount

                # Mark stuck running jobs as failed
                running_result = await self.db.execute(
                    update(AIGenerationJob)
                    .where(
                        and_(
                            AIGenerationJob.status == "running",
                            AIGenerationJob.started_at < running_threshold_time,
                            AIGenerationJob.completed_at.is_(None),
                        )
                    )
                    .values(
                        status="failed",
                        success=False,
                        error_message="Job stuck in running status for > 30 minutes. Automatically cleaned up.",
                        completed_at=datetime.utcnow(),
                    )
                )
                cleaned_running = running_result.rowcount

                await self.db.commit()

                logger.info(
                    f"Cleanup completed: {cleaned_queued} queued jobs and {cleaned_running} running jobs marked as failed"
                )

                return {
                    "action": action,
                    "cleaned_jobs": {
                        "queued": cleaned_queued,
                        "running": cleaned_running,
                        "total": cleaned_queued + cleaned_running,
                    },
                    "threshold_minutes": stuck_threshold_minutes,
                    "cleaned_at": datetime.utcnow().isoformat(),
                    "message": f"Successfully cleaned up {cleaned_queued + cleaned_running} stuck job(s).",
                }

            elif action == "retry":
                # TODO: Implement retry logic
                # This would require re-queuing jobs or restarting background tasks
                # For now, return not implemented
                return {
                    "action": action,
                    "message": "Retry action not yet implemented. Use 'mark_failed' to clean up stuck jobs.",
                    "cleaned_at": datetime.utcnow().isoformat(),
                }

            else:
                raise ValueError(
                    f"Invalid action: {action}. Must be 'mark_failed' or 'retry'"
                )

        except Exception as e:
            await self.db.rollback()
            logger.error("Failed to cleanup stuck jobs", error=str(e))
            raise

    async def log_admin_action(
        self,
        admin_id: int,
        action: str,
        target_type: str | None = None,
        target_id: int | None = None,
        old_value: dict | None = None,
        new_value: dict | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        correlation_id: str | None = None,
    ) -> AdminAuditLog:
        """
        Log an admin action to database and file.

        Args:
            admin_id: Admin user ID who performed the action
            action: Action name (e.g., "block_user", "approve_refund")
            target_type: Type of target (e.g., "user", "payment", "settings")
            target_id: ID of target entity
            old_value: Previous value (for updates)
            new_value: New value (for updates)
            ip_address: Admin IP address
            user_agent: Admin user agent
            correlation_id: Request correlation ID

        Returns:
            AdminAuditLog object
        """
        # Create audit log entry
        audit_log = AdminAuditLog(
            admin_id=admin_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            old_value=old_value,
            new_value=new_value,
            ip_address=ip_address,
            user_agent=user_agent,
            correlation_id=correlation_id,
        )

        self.db.add(audit_log)
        await self.db.commit()
        await self.db.refresh(audit_log)

        # Also log to file for quick search
        log_security_audit_event(
            event_type="admin_action",
            correlation_id=correlation_id or "unknown",
            user_id=admin_id,
            ip=ip_address or "unknown",
            resource=target_type or "unknown",
            action=action,
            outcome="success",
        )

        # Send alert for critical actions
        if action in CRITICAL_ACTIONS:
            logger.warning(
                f"CRITICAL_ADMIN_ACTION: admin_id={admin_id}, "
                f"action={action}, target_type={target_type}, target_id={target_id}",
                admin_id=admin_id,
                action=action,
                target_type=target_type,
                target_id=target_id,
                correlation_id=correlation_id,
            )
            # TODO: Implement actual alert sending (email, Slack, etc.)
            # await send_admin_alert(action, admin_id, target_type)

        return audit_log

    async def get_dashboard_charts(self, period: str = "week") -> dict[str, Any]:
        """
        Get chart data for dashboard graphs.

        Args:
            period: Time period (day, week, month, year)

        Returns:
            Dictionary with chart data for revenue, users, documents
        """
        try:
            # Calculate date range based on period
            if period == "day":
                days = 1
            elif period == "week":
                days = 7
            elif period == "month":
                days = 30
            elif period == "year":
                days = 365
            else:
                days = 7

            start_date = datetime.utcnow() - timedelta(days=days)

            # Revenue chart data (by date)
            revenue_data = []
            current_date = start_date.date()
            end_date = datetime.utcnow().date()

            while current_date <= end_date:
                next_date = current_date + timedelta(days=1)

                revenue_result = await self.db.execute(
                    select(func.sum(Payment.amount)).where(
                        and_(
                            Payment.status == "completed",
                            Payment.completed_at
                            >= datetime.combine(current_date, datetime.min.time()),
                            Payment.completed_at
                            < datetime.combine(next_date, datetime.min.time()),
                        )
                    )
                )
                daily_revenue = revenue_result.scalar() or 0

                revenue_data.append(
                    {
                        "date": current_date.isoformat(),
                        "revenue": float(daily_revenue),
                    }
                )

                current_date = next_date

            # Users growth chart data
            users_data = []
            current_date = start_date.date()

            while current_date <= end_date:
                next_date = current_date + timedelta(days=1)

                users_result = await self.db.execute(
                    select(func.count(User.id)).where(
                        and_(
                            User.created_at
                            >= datetime.combine(current_date, datetime.min.time()),
                            User.created_at
                            < datetime.combine(next_date, datetime.min.time()),
                        )
                    )
                )
                daily_users = users_result.scalar() or 0

                users_data.append(
                    {
                        "date": current_date.isoformat(),
                        "new_users": daily_users,
                    }
                )

                current_date = next_date

            # Documents chart data
            documents_data = []
            current_date = start_date.date()

            while current_date <= end_date:
                next_date = current_date + timedelta(days=1)

                docs_result = await self.db.execute(
                    select(func.count(Document.id)).where(
                        and_(
                            Document.created_at
                            >= datetime.combine(current_date, datetime.min.time()),
                            Document.created_at
                            < datetime.combine(next_date, datetime.min.time()),
                        )
                    )
                )
                daily_docs = docs_result.scalar() or 0

                documents_data.append(
                    {
                        "date": current_date.isoformat(),
                        "documents": daily_docs,
                    }
                )

                current_date = next_date

            return {
                "period": period,
                "revenue": revenue_data,
                "users": users_data,
                "documents": documents_data,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error("Failed to get dashboard charts", error=str(e))
            raise

    async def get_dashboard_activity(
        self, activity_type: str = "recent", limit: int = 10
    ) -> dict[str, Any]:
        """
        Get recent activity for dashboard.

        Args:
            activity_type: Type of activity (recent, payments, registrations, errors)
            limit: Number of items to return

        Returns:
            Dictionary with recent activity items
        """
        try:
            activities = []

            if activity_type == "recent" or activity_type == "payments":
                # Recent payments
                payments_result = await self.db.execute(
                    select(Payment)
                    .where(Payment.status == "completed")
                    .order_by(Payment.completed_at.desc())
                    .limit(limit)
                )
                payments = payments_result.scalars().all()

                for payment in payments:
                    activities.append(
                        {
                            "type": "payment",
                            "id": payment.id,
                            "user_id": payment.user_id,
                            "amount": float(payment.amount),
                            "currency": payment.currency,
                            "timestamp": payment.completed_at.isoformat()
                            if payment.completed_at
                            else payment.created_at.isoformat(),
                        }
                    )

            if activity_type == "recent" or activity_type == "registrations":
                # Recent user registrations
                users_result = await self.db.execute(
                    select(User).order_by(User.created_at.desc()).limit(limit)
                )
                users = users_result.scalars().all()

                for user in users:
                    activities.append(
                        {
                            "type": "registration",
                            "id": user.id,
                            "email": user.email,
                            "timestamp": user.created_at.isoformat(),
                        }
                    )

            if activity_type == "recent" or activity_type == "errors":
                # Recent failed AI jobs
                errors_result = await self.db.execute(
                    select(AIGenerationJob)
                    .where(AIGenerationJob.success.is_(False))
                    .order_by(AIGenerationJob.completed_at.desc())
                    .limit(limit)
                )
                errors = errors_result.scalars().all()

                for job in errors:
                    activities.append(
                        {
                            "type": "error",
                            "id": job.id,
                            "user_id": job.user_id,
                            "document_id": job.document_id,
                            "error_message": job.error_message,
                            "timestamp": job.completed_at.isoformat()
                            if job.completed_at
                            else job.started_at.isoformat(),
                        }
                    )

            # Sort by timestamp descending
            activities.sort(key=lambda x: x["timestamp"], reverse=True)
            activities = activities[:limit]

            return {
                "activity_type": activity_type,
                "activities": activities,
                "count": len(activities),
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error("Failed to get dashboard activity", error=str(e))
            raise

    async def get_dashboard_metrics(self) -> dict[str, Any]:
        """
        Get business metrics for dashboard (MRR, ARPU, etc.).

        Returns:
            Dictionary with business metrics
        """
        try:
            # Calculate MRR (Monthly Recurring Revenue)
            # For now, we'll use last 30 days revenue as MRR approximation
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)

            mrr_result = await self.db.execute(
                select(func.sum(Payment.amount)).where(
                    and_(
                        Payment.status == "completed",
                        Payment.completed_at >= thirty_days_ago,
                    )
                )
            )
            mrr = mrr_result.scalar() or 0

            # Calculate ARPU (Average Revenue Per User)
            total_users_result = await self.db.execute(
                select(func.count(User.id)).where(User.is_active.is_(True))
            )
            total_active_users = total_users_result.scalar() or 1

            arpu = float(mrr) / total_active_users if total_active_users > 0 else 0

            # Calculate conversion rate (registrations → payments)
            total_users_all_result = await self.db.execute(select(func.count(User.id)))
            total_users_all = total_users_all_result.scalar() or 1

            users_with_payments_result = await self.db.execute(
                select(func.count(func.distinct(Payment.user_id))).where(
                    Payment.status == "completed"
                )
            )
            users_with_payments = users_with_payments_result.scalar() or 0

            conversion_rate = (
                (users_with_payments / total_users_all) * 100
                if total_users_all > 0
                else 0
            )

            # Calculate churn rate (last 30 days)
            # Users who registered but haven't logged in for 30+ days
            churned_users_result = await self.db.execute(
                select(func.count(User.id)).where(
                    and_(
                        User.is_active.is_(True),
                        User.last_login < datetime.utcnow() - timedelta(days=30),
                        User.created_at < datetime.utcnow() - timedelta(days=30),
                    )
                )
            )
            churned_users = churned_users_result.scalar() or 0

            churn_rate = (
                (churned_users / total_active_users) * 100
                if total_active_users > 0
                else 0
            )

            # Refund rate
            total_refunds_result = await self.db.execute(
                select(func.count(RefundRequest.id)).where(
                    RefundRequest.status == "approved"
                )
            )
            total_refunds = total_refunds_result.scalar() or 0

            total_payments_result = await self.db.execute(
                select(func.count(Payment.id)).where(Payment.status == "completed")
            )
            total_payments = total_payments_result.scalar() or 1

            refund_rate = (
                (total_refunds / total_payments) * 100 if total_payments > 0 else 0
            )

            return {
                "mrr": float(mrr),
                "arpu": round(arpu, 2),
                "conversion_rate": round(conversion_rate, 2),
                "churn_rate": round(churn_rate, 2),
                "refund_rate": round(refund_rate, 2),
                "total_active_users": total_active_users,
                "users_with_payments": users_with_payments,
                "generated_at": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error("Failed to get dashboard metrics", error=str(e))
            raise
