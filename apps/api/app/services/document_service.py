"""
Document service for managing documents and sections
"""

from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.orm import selectinload
from app.models.document import Document, DocumentSection, DocumentOutline
from app.models.auth import User
from app.core.exceptions import NotFoundError, ValidationError
import logging

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
                update(User)
                .where(User.id == user_id)
                .values(total_documents_created=User.total_documents_created + 1)
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
            raise ValidationError(f"Failed to create document: {str(e)}")
    
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
            raise NotFoundError(f"Failed to get document: {str(e)}")
    
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
            raise ValidationError(f"Failed to get documents: {str(e)}")
    
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
            raise ValidationError(f"Failed to update document: {str(e)}")
    
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
            raise ValidationError(f"Failed to delete document: {str(e)}")
    
    async def get_document_sections(
        self,
        document_id: int,
        user_id: int
    ) -> List[Dict[str, Any]]:
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
            raise NotFoundError(f"Failed to get document sections: {str(e)}")
    
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
            raise ValidationError(f"Failed to update document content: {str(e)}")