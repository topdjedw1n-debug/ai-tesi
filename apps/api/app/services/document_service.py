"""
Document service for managing documents and sections
"""

import logging
from typing import Any, Dict, Optional

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError, ValidationError
from app.models.document import Document, DocumentSection

logger = logging.getLogger(__name__)


class DocumentService:
    """Service for document management"""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_document(
        self,
        user_id: int,
        title: str,
        topic: str,
        language: str = "en",
        target_pages: int = 10,
        ai_provider: str = "openai",
        ai_model: str = "gpt-4",
        additional_requirements: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a new document"""
        try:
            document = Document(
                user_id=user_id,
                title=title,
                topic=topic,
                language=language,
                target_pages=target_pages,
                ai_provider=ai_provider,
                ai_model=ai_model,
                status="draft"
            )

            self.db.add(document)
            await self.db.flush()  # Get the document ID

            # Update user's document count
            await self.db.execute(
                update(Document)
                .where(Document.user_id == user_id)
                .values(total_documents_created=Document.total_documents_created + 1)
            )

            await self.db.commit()

            return {
                "id": document.id,
                "title": document.title,
                "topic": document.topic,
                "status": document.status,
                "created_at": document.created_at.isoformat()
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating document: {e}")
            raise ValidationError(f"Failed to create document: {str(e)}") from e

    async def get_document(self, document_id: int, user_id: int) -> Dict[str, Any]:
        """Get document by ID"""
        try:
            result = await self.db.execute(
                select(Document)
                .options(selectinload(Document.sections))
                .where(
                    Document.id == document_id,
                    Document.user_id == user_id
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise NotFoundError("Document not found")

            return {
                "id": document.id,
                "title": document.title,
                "topic": document.topic,
                "language": document.language,
                "target_pages": document.target_pages,
                "status": document.status,
                "ai_provider": document.ai_provider,
                "ai_model": document.ai_model,
                "outline": document.outline,
                "content": document.content,
                "tokens_used": document.tokens_used,
                "generation_time_seconds": document.generation_time_seconds,
                "created_at": document.created_at.isoformat(),
                "updated_at": document.updated_at.isoformat(),
                "completed_at": document.completed_at.isoformat() if document.completed_at else None,
                "sections": [
                    {
                        "id": section.id,
                        "title": section.title,
                        "section_index": section.section_index,
                        "section_type": section.section_type,
                        "content": section.content,
                        "word_count": section.word_count,
                        "status": section.status,
                        "tokens_used": section.tokens_used,
                        "generation_time_seconds": section.generation_time_seconds,
                        "created_at": section.created_at.isoformat(),
                        "completed_at": section.completed_at.isoformat() if section.completed_at else None
                    }
                    for section in document.sections
                ]
            }

        except Exception as e:
            logger.error(f"Error getting document: {e}")
            raise NotFoundError(f"Failed to get document: {str(e)}") from e

    async def get_user_documents(
        self,
        user_id: int,
        limit: int = 20,
        offset: int = 0
    ) -> Dict[str, Any]:
        """Get user's documents with pagination"""
        try:
            # Get total count
            count_result = await self.db.execute(
                select(Document.id).where(Document.user_id == user_id)
            )
            total_count = len(count_result.scalars().all())

            # Get documents
            result = await self.db.execute(
                select(Document)
                .where(Document.user_id == user_id)
                .order_by(Document.created_at.desc())
                .limit(limit)
                .offset(offset)
            )
            documents = result.scalars().all()

            return {
                "documents": [
                    {
                        "id": doc.id,
                        "title": doc.title,
                        "topic": doc.topic,
                        "status": doc.status,
                        "tokens_used": doc.tokens_used,
                        "created_at": doc.created_at.isoformat(),
                        "updated_at": doc.updated_at.isoformat()
                    }
                    for doc in documents
                ],
                "total_count": total_count,
                "limit": limit,
                "offset": offset
            }

        except Exception as e:
            logger.error(f"Error getting user documents: {e}")
            raise ValidationError(f"Failed to get documents: {str(e)}") from e

    async def update_document(
        self,
        document_id: int,
        user_id: int,
        **updates
    ) -> Dict[str, Any]:
        """Update document"""
        try:
            # Check if document exists and belongs to user
            result = await self.db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.user_id == user_id
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise NotFoundError("Document not found")

            # Update allowed fields
            allowed_fields = [
                "title", "topic", "language", "target_pages",
                "ai_provider", "ai_model", "is_public"
            ]

            update_data = {k: v for k, v in updates.items() if k in allowed_fields}

            if update_data:
                await self.db.execute(
                    update(Document)
                    .where(Document.id == document_id)
                    .values(**update_data)
                )
                await self.db.commit()

            return {"message": "Document updated successfully"}

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating document: {e}")
            raise ValidationError(f"Failed to update document: {str(e)}") from e

    async def delete_document(self, document_id: int, user_id: int) -> Dict[str, Any]:
        """Delete document"""
        try:
            # Check if document exists and belongs to user
            result = await self.db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.user_id == user_id
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise NotFoundError("Document not found")

            # Delete document (cascade will handle sections)
            await self.db.execute(
                delete(Document).where(Document.id == document_id)
            )

            await self.db.commit()

            return {"message": "Document deleted successfully"}

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error deleting document: {e}")
            raise ValidationError(f"Failed to delete document: {str(e)}") from e

    async def get_document_sections(
        self,
        document_id: int,
        user_id: int
    ) -> list[Dict[str, Any]]:
        """Get all sections for a document"""
        try:
            # Verify document ownership
            result = await self.db.execute(
                select(Document.id).where(
                    Document.id == document_id,
                    Document.user_id == user_id
                )
            )
            if not result.scalar_one_or_none():
                raise NotFoundError("Document not found")

            # Get sections
            result = await self.db.execute(
                select(DocumentSection)
                .where(DocumentSection.document_id == document_id)
                .order_by(DocumentSection.section_index)
            )
            sections = result.scalars().all()

            return [
                {
                    "id": section.id,
                    "title": section.title,
                    "section_index": section.section_index,
                    "section_type": section.section_type,
                    "content": section.content,
                    "word_count": section.word_count,
                    "status": section.status,
                    "tokens_used": section.tokens_used,
                    "generation_time_seconds": section.generation_time_seconds,
                    "created_at": section.created_at.isoformat(),
                    "completed_at": section.completed_at.isoformat() if section.completed_at else None
                }
                for section in sections
            ]

        except Exception as e:
            logger.error(f"Error getting document sections: {e}")
            raise NotFoundError(f"Failed to get document sections: {str(e)}") from e

    async def update_document_content(
        self,
        document_id: int,
        user_id: int,
        content: str
    ) -> Dict[str, Any]:
        """Update document content"""
        try:
            # Verify document ownership
            result = await self.db.execute(
                select(Document).where(
                    Document.id == document_id,
                    Document.user_id == user_id
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise NotFoundError("Document not found")

            # Update content
            await self.db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(content=content, status="completed")
            )

            await self.db.commit()

            return {"message": "Document content updated successfully"}

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error updating document content: {e}")
            raise ValidationError(f"Failed to update document content: {str(e)}") from e

    async def verify_file_storage_integrity(self) -> Dict[str, Any]:
        """
        Verify file storage integrity (MinIO/S3).

        Checks:
        - Files referenced in database exist in storage
        - Orphaned files in storage (not referenced in DB)
        - File accessibility

        Returns:
            dict with missing_files count, orphaned_files list, and status
        """
        import time

        from minio import Minio
        from minio.error import S3Error

        from app.core.config import settings

        missing_files = []
        orphaned_files = []
        storage_files = []

        try:
            # Initialize MinIO client
            client = Minio(
                settings.MINIO_ENDPOINT,
                access_key=settings.MINIO_ACCESS_KEY,
                secret_key=settings.MINIO_SECRET_KEY,
                secure=settings.MINIO_SECURE
            )

            # Get all documents with file paths
            result = await self.db.execute(
                select(Document).where(
                    (Document.docx_path.isnot(None)) | (Document.pdf_path.isnot(None))
                )
            )
            documents = result.scalars().all()

            # Check files referenced in DB exist in storage
            for doc in documents:
                if doc.docx_path:
                    try:
                        # Extract object name from path
                        object_name = doc.docx_path.replace(f"s3://{settings.MINIO_BUCKET}/", "")
                        object_name = object_name.lstrip("/")
                        client.stat_object(settings.MINIO_BUCKET, object_name)
                    except S3Error:
                        missing_files.append({"document_id": doc.id, "file": doc.docx_path})

                if doc.pdf_path:
                    try:
                        object_name = doc.pdf_path.replace(f"s3://{settings.MINIO_BUCKET}/", "")
                        object_name = object_name.lstrip("/")
                        client.stat_object(settings.MINIO_BUCKET, object_name)
                    except S3Error:
                        missing_files.append({"document_id": doc.id, "file": doc.pdf_path})

            # List all files in bucket
            try:
                objects = client.list_objects(settings.MINIO_BUCKET, recursive=True)
                for obj in objects:
                    storage_files.append(obj.object_name)

                    # Check if file is referenced in DB
                    is_referenced = False
                    for doc in documents:
                        if doc.docx_path and obj.object_name in doc.docx_path:
                            is_referenced = True
                            break
                        if doc.pdf_path and obj.object_name in doc.pdf_path:
                            is_referenced = True
                            break

                    if not is_referenced:
                        orphaned_files.append(obj.object_name)
            except S3Error as e:
                logger.error(f"Error listing storage objects: {e}")

            # Determine status
            if len(missing_files) == 0 and len(orphaned_files) == 0:
                status = "healthy"
            elif len(missing_files) > 0:
                status = "critical"
            else:
                status = "needs_attention"

            return {
                "status": status,
                "missing_files": len(missing_files),
                "missing_file_details": missing_files[:10],  # Limit details
                "orphaned_files": len(orphaned_files),
                "orphaned_file_details": orphaned_files[:10],  # Limit details
                "total_storage_files": len(storage_files),
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error(f"Storage verification failed: {e}")
            return {
                "status": "error",
                "missing_files": 0,
                "orphaned_files": 0,
                "error": str(e),
                "timestamp": time.time()
            }
