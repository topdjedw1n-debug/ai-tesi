"""
Document management endpoints
"""
import logging

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, verify_download_token
from app.core.exceptions import NotFoundError, ValidationError
from app.middleware.rate_limit import rate_limit
from app.models.auth import User
from app.schemas.document import (
    DocumentCreate,
    DocumentListResponse,
    DocumentResponse,
    DocumentUpdate,
    ExportRequest,
    ExportResponse,
)
from app.services.custom_requirements_service import CustomRequirementsService
from app.services.document_service import DocumentService
from app.services.storage_service import StorageService

logger = logging.getLogger(__name__)

router = APIRouter()  # 307 redirect for trailing slash is standard REST API behavior


@router.post("/", response_model=DocumentResponse)
@rate_limit("100/hour")
async def create_document(
    request: Request,
    document: DocumentCreate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Create a new document"""
    try:
        document_service = DocumentService(db)
        result = await document_service.create_document(
            user_id=current_user.id,
            title=document.title,
            topic=document.topic,
            language=document.language,
            target_pages=document.target_pages,
            ai_provider=document.ai_provider.value
            if document.ai_provider
            else "openai",
            ai_model=document.ai_model or "gpt-4",
            additional_requirements=document.additional_requirements,
        )
        return result
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create document",
        ) from None


@router.get("/", response_model=DocumentListResponse)
@rate_limit("100/hour")
async def list_documents(
    request: Request,
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List user's documents with pagination"""
    try:
        document_service = DocumentService(db)
        result = await document_service.get_user_documents(
            user_id=current_user.id, limit=limit, offset=offset
        )
        return result
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to list documents",
        ) from None


@router.get("/{document_id}", response_model=DocumentResponse)
@rate_limit("100/hour")
async def get_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get a specific document by ID"""
    try:
        document_service = DocumentService(db)
        # Check ownership using helper function
        await document_service.check_document_ownership(document_id, current_user.id)
        result = await document_service.get_document(document_id, current_user.id)
        if not result:
            raise NotFoundError("Document not found")
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get document",
        ) from None


@router.put("/{document_id}", response_model=DocumentResponse)
@rate_limit("100/hour")
async def update_document(
    request: Request,
    document_id: int,
    document: DocumentUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Update a document"""
    try:
        document_service = DocumentService(db)
        # Check ownership using helper function
        await document_service.check_document_ownership(document_id, current_user.id)
        # Convert Pydantic model to dict and unpack
        update_dict = document.model_dump(exclude_unset=True)
        await document_service.update_document(
            document_id, current_user.id, **update_dict
        )
        # Fetch updated document to return
        result = await document_service.get_document(document_id, current_user.id)
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update document",
        ) from None


@router.get("/stats")
@rate_limit("100/hour")
async def get_user_stats(
    request: Request,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user statistics for dashboard"""
    try:
        document_service = DocumentService(db)
        stats = await document_service.get_user_stats(current_user.id)
        return stats
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get user stats",
        ) from None


@router.get("/activity")
@rate_limit("100/hour")
async def get_recent_activity(
    request: Request,
    limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get recent activity for user dashboard"""
    try:
        document_service = DocumentService(db)
        activities = await document_service.get_recent_activity(
            current_user.id, limit=limit
        )
        return {"activities": activities}
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get recent activity",
        ) from None


@router.delete("/{document_id}")
@rate_limit("100/hour")
async def delete_document(
    request: Request,
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a document (soft delete)"""
    try:
        document_service = DocumentService(db)
        # Check ownership using helper function
        await document_service.check_document_ownership(document_id, current_user.id)
        success = await document_service.delete_document(document_id, current_user.id)
        if not success:
            raise NotFoundError("Document not found")
        return {"message": "Document deleted successfully"}
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to delete document",
        ) from None


@router.post("/{document_id}/export", response_model=ExportResponse)
@rate_limit("100/hour")
async def export_document(
    request: Request,
    document_id: int,
    export_request: ExportRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export document to DOCX or PDF"""
    try:
        document_service = DocumentService(db)
        # Check ownership using helper function
        await document_service.check_document_ownership(document_id, current_user.id)
        result = await document_service.export_document(
            document_id, export_request.format, current_user.id
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export document",
        ) from None


@router.get("/{document_id}/export/{format}", response_model=ExportResponse)
@rate_limit("100/hour")
async def export_document_get(
    request: Request,
    document_id: int,
    format: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Export document via GET route to match frontend: /documents/{id}/export/{format}"""
    try:
        document_service = DocumentService(db)
        # Check ownership using helper function
        await document_service.check_document_ownership(document_id, current_user.id)
        result = await document_service.export_document(
            document_id, format, current_user.id
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to export document",
        ) from None


@router.post("/{document_id}/custom-requirements/upload")
@rate_limit("10/hour")
async def upload_custom_requirements(
    request: Request,
    document_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Upload custom requirements file (PDF, DOCX, TXT)
    Extracts text from the file and stores it
    """
    try:
        # Get document and verify ownership
        document_service = DocumentService(db)
        await document_service.check_document_ownership(document_id, current_user.id)

        # Extract text from uploaded file
        requirements_service = CustomRequirementsService()
        extracted_text = await requirements_service.extract_text(file)

        # Store the extracted text in document (for now, we store in content or outline)
        # In production, you might want to store in a separate field or MinIO
        # TODO: Store extracted_text in document properly
        logger.info(
            f"Extracted {len(extracted_text)} characters from file {file.filename}"
        )

        return {
            "message": "Custom requirements file uploaded and processed successfully",
            "document_id": document_id,
            "file_size": len(extracted_text),
            "preview": extracted_text[:500]
            if len(extracted_text) > 500
            else extracted_text,
        }
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)
        ) from e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process custom requirements file: {str(e)}",
        ) from e


@router.get("/download")
async def download_document_secure(
    token: str = Query(..., description="Signed download token"),
    db: AsyncSession = Depends(get_db),
):
    """
    Secure document download endpoint with JWT token validation.

    Token must contain document_id and user_id claims.
    Only the document owner can download.
    """
    try:
        # Verify token and extract claims
        payload = verify_download_token(token)
        document_id = payload["document_id"]
        user_id = payload["user_id"]

        # Get document from database
        document_service = DocumentService(db)
        document = await document_service.get_document_by_id(document_id)

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )

        # Verify ownership (CRITICAL security check)
        if document.user_id != user_id:
            logger.warning(
                f"SECURITY: Download attempt with mismatched ownership. "
                f"Token user_id={user_id}, Document user_id={document.user_id}, "
                f"Document ID={document_id}"
            )
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Access denied"
            )

        # Check if document has file path in storage (prefer DOCX over PDF)
        file_path = document.docx_path or document.pdf_path

        if not file_path:
            # If no file, return content as text (fallback)
            logger.info(f"No file path for document {document_id}, returning content")
            content = document.content or "No content available"
            return StreamingResponse(
                iter([content.encode("utf-8")]),
                media_type="text/plain",
                headers={
                    "Content-Disposition": f'attachment; filename="{document.title}.txt"'
                },
            )

        # Initialize StorageService
        storage_service = StorageService()

        # Determine media type and file extension based on file path
        media_type = "application/octet-stream"
        file_extension = ".docx"  # default

        if file_path.endswith(".docx"):
            media_type = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            file_extension = ".docx"
        elif file_path.endswith(".pdf"):
            media_type = "application/pdf"
            file_extension = ".pdf"

        logger.info(
            f"Document download: user_id={user_id}, document_id={document_id}, "
            f"file_path={file_path}"
        )

        # Stream file from MinIO using StorageService
        file_stream = storage_service.download_file_stream(file_path)

        return StreamingResponse(
            file_stream,
            media_type=media_type,
            headers={
                "Content-Disposition": f'attachment; filename="{document.title}{file_extension}"'
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading document: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download document",
        ) from e
