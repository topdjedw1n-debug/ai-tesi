"""
Document management endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Optional
from app.core.database import get_db
from app.schemas.document import (
    DocumentCreate,
    DocumentUpdate,
    DocumentResponse,
    DocumentListResponse,
    ExportRequest,
    ExportResponse
)
from app.services.document_service import DocumentService
from app.core.exceptions import NotFoundError, ValidationError
from app.middleware.rate_limit import limiter

router = APIRouter()


@router.post("/", response_model=DocumentResponse)
@limiter.limit("100/hour")
async def create_document(
    document: DocumentCreate,
    db: AsyncSession = Depends(get_db)
):
    """Create a new document"""
    try:
        # TODO: Get current user from authentication
        user_id = 1  # Placeholder
        
        document_service = DocumentService(db)
        result = await document_service.create_document(
            user_id=user_id,
            title=document.title,
            topic=document.topic,
            language=document.language,
            target_pages=document.target_pages,
            ai_provider=document.ai_provider,
            ai_model=document.ai_model,
            additional_requirements=document.additional_requirements
        )
        return result
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create document"
        )


@router.get("/", response_model=DocumentListResponse)
@limiter.limit("100/hour")
async def list_documents(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db)
):
    """List user's documents with pagination"""
    try:
        # TODO: Get current user from authentication
        user_id = 1  # Placeholder
        
        document_service = DocumentService(db)
        result = await document_service.get_user_documents(
            user_id=user_id,
            limit=limit,
            offset=offset
        )
        return result
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents"
        )


@router.get("/{document_id}", response_model=DocumentResponse)
@limiter.limit("100/hour")
async def get_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get a specific document by ID"""
    try:
        # TODO: Get current user from authentication
        user_id = 1  # Placeholder
        
        document_service = DocumentService(db)
        result = await document_service.get_document(document_id, user_id)
        if not result:
            raise NotFoundError("Document not found")
        return result
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document"
        )


@router.put("/{document_id}", response_model=DocumentResponse)
@limiter.limit("100/hour")
async def update_document(
    document_id: int,
    document: DocumentUpdate,
    db: AsyncSession = Depends(get_db)
):
    """Update a document"""
    try:
        # TODO: Get current user from authentication
        user_id = 1  # Placeholder
        
        document_service = DocumentService(db)
        result = await document_service.update_document(document_id, document, user_id)
        if not result:
            raise NotFoundError("Document not found")
        return result
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document"
        )


@router.delete("/{document_id}")
@limiter.limit("100/hour")
async def delete_document(
    document_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Delete a document (soft delete)"""
    try:
        # TODO: Get current user from authentication
        user_id = 1  # Placeholder
        
        document_service = DocumentService(db)
        success = await document_service.delete_document(document_id, user_id)
        if not success:
            raise NotFoundError("Document not found")
        return {"message": "Document deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document"
        )


@router.post("/{document_id}/export", response_model=ExportResponse)
@limiter.limit("100/hour")
async def export_document(
    document_id: int,
    export_request: ExportRequest,
    db: AsyncSession = Depends(get_db)
):
    """Export document to DOCX or PDF"""
    try:
        # TODO: Get current user from authentication
        user_id = 1  # Placeholder
        
        document_service = DocumentService(db)
        result = await document_service.export_document(
            document_id, 
            export_request.format,
            user_id
        )
        return result
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export document"
        )


@router.get("/{document_id}/export/{format}", response_model=ExportResponse)
@limiter.limit("100/hour")
async def export_document_get(
    document_id: int,
    format: str,
    db: AsyncSession = Depends(get_db)
):
    """Export document via GET route to match frontend: /documents/{id}/export/{format}"""
    try:
        # TODO: Get current user from authentication
        user_id = 1  # Placeholder

        document_service = DocumentService(db)
        result = await document_service.export_document(
            document_id,
            format,
            user_id
        )
        return result
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export document"
        )
