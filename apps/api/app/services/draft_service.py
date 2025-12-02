"""
Draft service for auto-save functionality
"""

import logging
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy import delete, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.models.document import Document, DocumentDraft

logger = logging.getLogger(__name__)

# Configuration constants
MAX_DRAFT_VERSIONS = 10
DRAFT_RETENTION_DAYS = 30


class DraftService:
    """Service for document draft management and auto-save"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_draft(
        self, document_id: int, user_id: int, content: str | None = None
    ) -> dict[str, Any]:
        """
        Save a draft version of a document.
        Automatically manages version count and old draft cleanup.

        Args:
            document_id: ID of the document
            user_id: ID of the user (for ownership verification)
            content: Draft content to save (can be None for auto-save)

        Returns:
            dict with draft_id, version, and created_at
        """
        # Verify document ownership
        result = await self.db.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user_id
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            raise NotFoundError("Document not found")

        # Get the next version number
        version_result = await self.db.execute(
            select(func.max(DocumentDraft.version)).where(
                DocumentDraft.document_id == document_id
            )
        )
        max_version = version_result.scalar() or 0
        next_version = max_version + 1

        # Create new draft
        draft = DocumentDraft(
            document_id=document_id,
            user_id=user_id,
            content=content,
            version=next_version,
            auto_save=True,
        )

        self.db.add(draft)
        await self.db.flush()

        # Cleanup old drafts (keep only last MAX_DRAFT_VERSIONS)
        await self._cleanup_old_drafts(document_id, user_id)

        # Cleanup drafts older than retention period
        await self._cleanup_expired_drafts()

        await self.db.commit()

        logger.info(
            f"Saved draft version {next_version} for document {document_id} by user {user_id}"
        )

        return {
            "id": draft.id,
            "document_id": draft.document_id,
            "version": draft.version,
            "created_at": draft.created_at,
        }

    async def get_latest_draft(
        self, document_id: int, user_id: int
    ) -> dict[str, Any] | None:
        """
        Get the latest draft for a document.

        Args:
            document_id: ID of the document
            user_id: ID of the user (for ownership verification)

        Returns:
            dict with draft data or None if no draft exists
        """
        # Verify document ownership
        result = await self.db.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user_id
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            raise NotFoundError("Document not found")

        # Get latest draft
        draft_result = await self.db.execute(
            select(DocumentDraft)
            .where(
                DocumentDraft.document_id == document_id,
                DocumentDraft.user_id == user_id,
            )
            .order_by(desc(DocumentDraft.version))
            .limit(1)
        )
        draft = draft_result.scalar_one_or_none()

        if not draft:
            return None

        return {
            "id": draft.id,
            "document_id": draft.document_id,
            "content": draft.content,
            "version": draft.version,
            "created_at": draft.created_at,
        }

    async def get_recoverable_documents(self, user_id: int) -> list[dict[str, Any]]:
        """
        Get list of documents with status 'generating' that can be recovered.

        Args:
            user_id: ID of the user

        Returns:
            list of documents with recovery information
        """
        # Find documents with status 'generating' that belong to user
        result = await self.db.execute(
            select(Document)
            .where(Document.user_id == user_id, Document.status == "generating")
            .order_by(desc(Document.updated_at))
        )
        documents = result.scalars().all()

        recoverable = []
        for doc in documents:
            # Check if there's a draft available
            draft_result = await self.db.execute(
                select(DocumentDraft)
                .where(DocumentDraft.document_id == doc.id)
                .order_by(desc(DocumentDraft.version))
                .limit(1)
            )
            draft = draft_result.scalar_one_or_none()

            recoverable.append(
                {
                    "document_id": doc.id,
                    "title": doc.title,
                    "status": doc.status,
                    "updated_at": doc.updated_at,
                    "has_draft": draft is not None,
                    "latest_draft_version": draft.version if draft else None,
                    "latest_draft_at": draft.created_at if draft else None,
                }
            )

        return recoverable

    async def recover_document_from_draft(
        self, document_id: int, user_id: int
    ) -> dict[str, Any]:
        """
        Recover a document from its latest draft.

        Args:
            document_id: ID of the document to recover
            user_id: ID of the user (for ownership verification)

        Returns:
            dict with recovery information
        """
        # Verify document ownership
        result = await self.db.execute(
            select(Document).where(
                Document.id == document_id, Document.user_id == user_id
            )
        )
        document = result.scalar_one_or_none()

        if not document:
            raise NotFoundError("Document not found")

        # Get latest draft
        draft_result = await self.db.execute(
            select(DocumentDraft)
            .where(
                DocumentDraft.document_id == document_id,
                DocumentDraft.user_id == user_id,
            )
            .order_by(desc(DocumentDraft.version))
            .limit(1)
        )
        draft = draft_result.scalar_one_or_none()

        if not draft:
            raise NotFoundError("No draft found for this document")

        # Restore document content from draft
        document.content = draft.content
        document.status = "draft"  # Reset status to draft
        document.updated_at = datetime.now()

        await self.db.commit()

        logger.info(
            f"Recovered document {document_id} from draft version {draft.version}"
        )

        return {
            "document_id": document.id,
            "recovered_from_version": draft.version,
            "recovered_at": draft.created_at,
            "status": document.status,
        }

    async def _cleanup_old_drafts(self, document_id: int, user_id: int) -> None:
        """
        Clean up old drafts, keeping only the last MAX_DRAFT_VERSIONS versions.

        Args:
            document_id: ID of the document
            user_id: ID of the user
        """
        # Get all drafts ordered by version (descending)
        drafts_result = await self.db.execute(
            select(DocumentDraft)
            .where(
                DocumentDraft.document_id == document_id,
                DocumentDraft.user_id == user_id,
            )
            .order_by(desc(DocumentDraft.version))
        )
        all_drafts = drafts_result.scalars().all()

        # If we have more than MAX_DRAFT_VERSIONS, delete the oldest ones
        if len(all_drafts) > MAX_DRAFT_VERSIONS:
            drafts_to_delete = all_drafts[MAX_DRAFT_VERSIONS:]
            draft_ids_to_delete = [d.id for d in drafts_to_delete]

            await self.db.execute(
                delete(DocumentDraft).where(DocumentDraft.id.in_(draft_ids_to_delete))
            )

            logger.debug(
                f"Deleted {len(drafts_to_delete)} old drafts for document {document_id}"
            )

    async def _cleanup_expired_drafts(self) -> None:
        """
        Clean up drafts older than DRAFT_RETENTION_DAYS.
        This is called automatically on each save.
        """
        cutoff_date = datetime.now() - timedelta(days=DRAFT_RETENTION_DAYS)

        result = await self.db.execute(
            delete(DocumentDraft).where(DocumentDraft.created_at < cutoff_date)
        )

        deleted_count = result.rowcount
        if deleted_count > 0:
            logger.info(
                f"Cleaned up {deleted_count} expired drafts (older than {DRAFT_RETENTION_DAYS} days)"
            )

