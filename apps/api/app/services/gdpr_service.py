"""
GDPR compliance service for data export and account deletion
"""

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.auth import MagicLinkToken, User, UserConsent, UserSession
from app.models.document import (
    AIGenerationJob,
    Document,
    DocumentSection,
    ProductionCase,
)
from app.models.payment import Payment

logger = logging.getLogger(__name__)


class GDPRService:
    """Service for GDPR compliance operations"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def export_user_data(self, user_id: int) -> dict[str, Any]:
        """
        Export all user data for GDPR compliance.
        Returns comprehensive JSON with all user-related data.

        Args:
            user_id: ID of the user

        Returns:
            dict containing all user data
        """
        try:
            # Get user
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise NotFoundError("User not found")

            # Get user documents
            documents_result = await self.db.execute(
                select(Document).where(Document.user_id == user_id)
            )
            documents = documents_result.scalars().all()

            # Get document sections
            document_ids = [doc.id for doc in documents]
            sections = []
            if document_ids:
                sections_result = await self.db.execute(
                    select(DocumentSection).where(
                        DocumentSection.document_id.in_(document_ids)
                    )
                )
                sections: list[Any] = sections_result.scalars().all()

            # Get payments
            payments_result = await self.db.execute(
                select(Payment).where(Payment.user_id == user_id)
            )
            payments = payments_result.scalars().all()

            # Get consents
            consents_result = await self.db.execute(
                select(UserConsent).where(UserConsent.user_id == user_id)
            )
            consents = consents_result.scalars().all()

            # Build export data
            export_data = {
                "user": {
                    "id": user.id,
                    "email": user.email,
                    "full_name": user.full_name,
                    "is_active": user.is_active,
                    "is_verified": user.is_verified,
                    "preferred_language": user.preferred_language,
                    "timezone": user.timezone,
                    "total_tokens_used": user.total_tokens_used,
                    "total_documents_created": user.total_documents_created,
                    "total_cost": user.total_cost,
                    "created_at": user.created_at.isoformat()
                    if user.created_at
                    else None,
                    "updated_at": user.updated_at.isoformat()
                    if user.updated_at
                    else None,
                    "last_login": user.last_login.isoformat()
                    if user.last_login
                    else None,
                },
                "documents": [
                    {
                        "id": doc.id,
                        "title": doc.title,
                        "topic": doc.topic,
                        "language": doc.language,
                        "target_pages": doc.target_pages,
                        "status": doc.status,
                        "is_public": doc.is_public,
                        "is_archived": doc.is_archived,
                        "ai_provider": doc.ai_provider,
                        "ai_model": doc.ai_model,
                        "tokens_used": doc.tokens_used,
                        "generation_time_seconds": doc.generation_time_seconds,
                        "created_at": doc.created_at.isoformat()
                        if doc.created_at
                        else None,
                        "updated_at": doc.updated_at.isoformat()
                        if doc.updated_at
                        else None,
                        "completed_at": doc.completed_at.isoformat()
                        if doc.completed_at
                        else None,
                    }
                    for doc in documents
                ],
                "sections": [
                    {
                        "id": section.id,
                        "document_id": section.document_id,
                        "title": section.title,
                        "section_index": section.section_index,
                        "section_type": section.section_type,
                        "word_count": section.word_count,
                        "status": section.status,
                        "tokens_used": section.tokens_used,
                        "created_at": section.created_at.isoformat()
                        if section.created_at
                        else None,
                    }
                    for section in sections
                ],
                "payments": [
                    {
                        "id": payment.id,
                        "amount": payment.amount,
                        "currency": payment.currency,
                        "status": payment.status,
                        "stripe_payment_intent_id": payment.stripe_payment_intent_id,
                        "created_at": payment.created_at.isoformat()
                        if payment.created_at
                        else None,
                    }
                    for payment in payments
                ],
                "consents": [
                    {
                        "id": consent.id,
                        "consent_type": consent.consent_type,
                        "granted": consent.consented,
                        "granted_at": consent.created_at.isoformat()
                        if consent.created_at
                        else None,
                        "revoked_at": consent.updated_at.isoformat()
                        if not consent.consented
                        and consent.updated_at != consent.created_at
                        else None,
                        "ip_address": consent.ip_address,
                    }
                    for consent in consents
                ],
                "export_metadata": {
                    "exported_at": datetime.now().isoformat(),
                    "user_id": user_id,
                    "data_version": "1.0",
                },
            }

            logger.info(f"Exported user data for user {user_id}")

            return export_data

        except Exception as e:
            logger.error(f"Error exporting user data: {e}")
            raise ValidationError(f"Failed to export user data: {str(e)}") from e

    async def delete_user_account(self, user_id: int) -> dict[str, Any]:
        """
        Delete user account (anonymize instead of hard delete for GDPR compliance).
        Removes sensitive data and files.

        Args:
            user_id: ID of the user

        Returns:
            dict with deletion status
        """
        try:
            # Phase 1 persists the user's privacy intent before any slow storage
            # call. The row lock serializes compliant enqueue paths; migration
            # 023 is the database backstop for any path that forgets the lock.
            marker_result = await self.db.execute(
                select(User)
                .where(User.id == user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            marker_user = marker_result.scalar_one_or_none()
            if marker_user is None:
                raise NotFoundError("User not found")
            if marker_user.deletion_requested_at is None:
                marker_user.deletion_requested_at = datetime.now(UTC)
            await self.db.commit()

            # Phase 2 reacquires the same user lock and holds it until account
            # cleanup finishes. A failure rolls back cleanup, not the durable
            # deletion marker committed above.
            user_result = await self.db.execute(
                select(User)
                .where(User.id == user_id)
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            user = user_result.scalar_one_or_none()
            if user is None:
                raise NotFoundError("User not found")

            original_email = str(user.email)

            # Worker/export fencing owns Job before Document. Inspect and lock
            # active jobs first; if one exists, return before touching documents.
            # The durable marker + trigger prevent a completed job from being
            # reactivated or a new job from appearing after this check.
            active_job = (
                await self.db.execute(
                    select(AIGenerationJob.id)
                    .where(
                        AIGenerationJob.user_id == user_id,
                        AIGenerationJob.status.in_(["queued", "running"]),
                    )
                    .order_by(AIGenerationJob.id.asc())
                    .with_for_update()
                    .limit(1)
                )
            ).scalar_one_or_none()
            if active_job is not None:
                raise ValidationError(
                    "Account deletion is pending while document generation is active; "
                    "retry deletion after the active job finishes"
                )

            # No active job remains. Lock the complete job history before the
            # documents so deferred cleanup paths from an earlier regeneration
            # cannot disappear with the SQL rows while their blobs survive.
            generation_jobs_result = await self.db.execute(
                select(AIGenerationJob)
                .where(AIGenerationJob.user_id == user_id)
                .order_by(AIGenerationJob.id.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            generation_jobs = list(generation_jobs_result.scalars().all())

            # Lock the stable document/case snapshot in deterministic order
            # before deleting any referenced storage object.
            documents_result = await self.db.execute(
                select(Document)
                .where(Document.user_id == user_id)
                .order_by(Document.id.asc())
                .with_for_update()
                .execution_options(populate_existing=True)
            )
            documents = list(documents_result.scalars().all())
            document_ids = [int(document.id) for document in documents]
            if document_ids:
                cases_result = await self.db.execute(
                    select(ProductionCase.id)
                    .where(ProductionCase.document_id.in_(document_ids))
                    .order_by(ProductionCase.id.asc())
                    .with_for_update()
                )
                cases_result.all()

            # The locked rows are now a stable file snapshot. New jobs are
            # blocked by the durable marker, so no later generation can add a path.

            # Delete every referenced file before removing its database record.
            # A storage failure must abort the account deletion so we never claim
            # that personal data was deleted while a required blob still exists.
            referenced_paths: list[str] = []
            for doc in documents:
                referenced_paths.extend(
                    str(file_path)
                    for file_path in (
                        doc.docx_path,
                        doc.pdf_path,
                        doc.custom_requirements_file_path,
                    )
                    if file_path
                )

            for job in generation_jobs:
                payload = (
                    job.request_payload if isinstance(job.request_payload, dict) else {}
                )
                superseded_paths = payload.get("superseded_artifact_paths")
                if isinstance(superseded_paths, list):
                    referenced_paths.extend(
                        str(path) for path in superseded_paths if path
                    )

            deleted_files: list[str] = []
            for path in dict.fromkeys(referenced_paths):
                await self._delete_from_storage(path)
                deleted_files.append(path)
                logger.info("Deleted user file: %s", path)

            # Anonymize user data instead of hard delete
            user.email = f"deleted_{user.id}@deleted.com"  # type: ignore[assignment]
            user.full_name = "DELETED USER"  # type: ignore[assignment]
            user.is_active = False  # type: ignore[assignment]
            user.stripe_customer_id = None  # type: ignore[assignment]

            # Delete consents (sensitive data)
            await self.db.execute(
                delete(UserConsent).where(UserConsent.user_id == user_id)
            )
            await self.db.execute(
                delete(UserSession).where(UserSession.user_id == user_id)
            )
            await self.db.execute(
                delete(MagicLinkToken).where(MagicLinkToken.email == original_email)
            )

            # Completed/failed job history can contain prompts and errors. It is
            # personal data too, including rows whose document_id is already NULL.
            await self.db.execute(
                delete(AIGenerationJob).where(AIGenerationJob.user_id == user_id)
            )

            # Delete documents (cascade will handle sections)
            await self.db.execute(delete(Document).where(Document.user_id == user_id))

            # Delete payments (if needed, or anonymize)
            # For now, we'll keep payment records but remove user association
            # await self.db.execute(delete(Payment).where(Payment.user_id == user_id))

            await self.db.commit()

            logger.info(f"Deleted account for user {user_id}, anonymized data")

            return {
                "status": "account_deleted",
                "user_id": user_id,
                "deleted_at": datetime.now(UTC).isoformat(),
                "files_deleted": len(deleted_files),
            }

        except (NotFoundError, ValidationError):
            await self.db.rollback()
            raise
        except Exception as e:
            # deletion_requested_at was committed in phase 1 and intentionally
            # survives this rollback so no new personal data can be generated.
            await self.db.rollback()
            logger.error("Error deleting user account: %s", e)
            raise ValidationError(f"Failed to delete account: {str(e)}") from e

    async def _delete_from_storage(self, file_path: str) -> bool:
        """
        Delete file from MinIO/S3 storage.

        Args:
            file_path: Path to file in storage (e.g., "s3://bucket/path/to/file.pdf")
        """
        from app.services.storage_service import StorageService

        storage_service = StorageService()
        success = await storage_service.delete_file(file_path)
        if not success:
            raise RuntimeError(f"Storage did not confirm deletion: {file_path}")

        logger.info("Deleted file from storage: %s", file_path)
        return True
