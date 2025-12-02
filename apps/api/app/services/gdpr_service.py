"""
GDPR compliance service for data export and account deletion
"""

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.models.auth import User, UserConsent
from app.models.document import Document, DocumentSection
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
                sections = sections_result.scalars().all()

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
                        "granted": consent.granted,
                        "granted_at": consent.granted_at.isoformat()
                        if consent.granted_at
                        else None,
                        "revoked_at": consent.revoked_at.isoformat()
                        if consent.revoked_at
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
            # Get user
            result = await self.db.execute(select(User).where(User.id == user_id))
            user = result.scalar_one_or_none()

            if not user:
                raise NotFoundError("User not found")

            # Get user documents for file deletion
            documents_result = await self.db.execute(
                select(Document).where(Document.user_id == user_id)
            )
            documents = documents_result.scalars().all()

            # Delete files from storage (MinIO/S3)
            deleted_files = []
            for doc in documents:
                if doc.docx_path:
                    await self._delete_from_storage(doc.docx_path)
                    deleted_files.append(doc.docx_path)
                    logger.info(f"Deleted DOCX: {doc.docx_path}")

                if doc.pdf_path:
                    await self._delete_from_storage(doc.pdf_path)
                    deleted_files.append(doc.pdf_path)
                    logger.info(f"Deleted PDF: {doc.pdf_path}")

            # Anonymize user data instead of hard delete
            user.email = f"deleted_{user.id}@deleted.com"
            user.full_name = "DELETED USER"
            user.is_active = False
            user.stripe_customer_id = None

            # Delete consents (sensitive data)
            await self.db.execute(
                delete(UserConsent).where(UserConsent.user_id == user_id)
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
                "deleted_at": datetime.now().isoformat(),
                "files_deleted": len(deleted_files),
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting user account: {e}")
            raise ValidationError(f"Failed to delete account: {str(e)}") from e

    async def _delete_from_storage(self, file_path: str) -> None:
        """
        Delete file from MinIO/S3 storage.

        Args:
            file_path: Path to file in storage (e.g., "s3://bucket/path/to/file.pdf")
        """
        try:
            from app.services.storage_service import StorageService

            # Initialize StorageService
            storage_service = StorageService()

            # Delete file using StorageService (silent mode for GDPR)
            success = await storage_service.delete_file(file_path, silent=True)

            if success:
                logger.info(f"✅ Deleted file from storage: {file_path}")
            else:
                logger.warning(f"File deletion failed or not found: {file_path}")

        except Exception as e:
            logger.error(f"Error deleting file from storage {file_path}: {e}")
            # Don't raise - continue with other deletions
