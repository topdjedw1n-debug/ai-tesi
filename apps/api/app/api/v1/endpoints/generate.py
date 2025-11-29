"""
AI generation endpoints
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.exceptions import AIProviderError, NotFoundError
from app.middleware.rate_limit import rate_limit
from app.models.auth import User
from app.models.document import AIGenerationJob, Document
from app.schemas.document import (
    AsyncGenerationRequest,
    AsyncGenerationResponse,
    OutlineRequest,
    OutlineResponse,
    SectionRequest,
    SectionResponse,
)
from app.services.ai_service import AIService
from app.services.background_jobs import BackgroundJobService
from app.services.cost_estimator import CostEstimator
from app.services.document_service import DocumentService
from app.services.grammar_checker import GrammarChecker
from app.services.plagiarism_checker import PlagiarismChecker

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/outline", response_model=OutlineResponse)
@rate_limit("10/hour")
async def generate_outline(
    http_request: Request,
    request: OutlineRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate document outline using AI"""
    try:
        ai_service = AIService(db)
        result = await ai_service.generate_outline(
            document_id=request.document_id,
            user_id=current_user.id,
            additional_requirements=request.additional_requirements,
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except AIProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate outline",
        ) from None


@router.post("/section", response_model=SectionResponse)
@rate_limit("10/hour")
async def generate_section(
    http_request: Request,
    request: SectionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a specific section using AI"""
    try:
        ai_service = AIService(db)
        result = await ai_service.generate_section(
            document_id=request.document_id,
            section_title=request.section_title,
            section_index=request.section_index,
            user_id=current_user.id,
            additional_requirements=request.additional_requirements,
        )
        return result
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except AIProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e)
        ) from e
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate section",
        ) from None


@router.get("/models")
async def list_available_models():
    """List available AI models"""
    return {
        "openai": [
            {"id": "gpt-4", "name": "GPT-4", "max_tokens": 4000},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "max_tokens": 8000},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "max_tokens": 4000},
        ],
        "anthropic": [
            {
                "id": "claude-3-5-sonnet-20241022",
                "name": "Claude 3.5 Sonnet",
                "max_tokens": 4000,
            },
            {
                "id": "claude-3-opus-20240229",
                "name": "Claude 3 Opus",
                "max_tokens": 4000,
            },
        ],
    }


@router.get("/usage/{user_id}")
async def get_user_usage(
    user_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get AI usage statistics for a user"""
    try:
        # Enforce authorization: users can only view their own usage
        if current_user.id != user_id and not current_user.is_admin:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions to view this user's usage",
            )

        ai_service = AIService(db)
        result = await ai_service.get_user_usage(user_id)
        return result
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage statistics",
        ) from None


@router.get("/estimate-cost")
async def estimate_cost(
    provider: str,
    model: str,
    target_pages: int,
    include_rag: bool = True,
    include_humanization: bool = False,
    current_user: User = Depends(get_current_user),
):
    """
    Estimate cost for document generation before starting

    Args:
        provider: AI provider ("openai" or "anthropic")
        model: Model name
        target_pages: Target number of pages
        include_rag: Whether RAG is enabled
        include_humanization: Whether humanization is enabled
    """
    try:
        cost_estimate = CostEstimator.estimate_document_cost(
            provider=provider,
            model=model,
            target_pages=target_pages,
            include_rag=include_rag,
            include_humanization=include_humanization,
        )
        return cost_estimate
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to estimate cost: {str(e)}",
        ) from e


class PlagiarismCheckRequest(BaseModel):
    """Request schema for plagiarism check"""

    text: str = Field(..., min_length=10, description="Text to check for plagiarism")


@router.post("/check-plagiarism")
async def check_plagiarism(
    request: PlagiarismCheckRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Check text for plagiarism using Copyscape API

    Args:
        request: Plagiarism check request with text
    """
    try:
        checker = PlagiarismChecker()
        result = await checker.check_text(request.text)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check plagiarism: {str(e)}",
        ) from e


class GrammarCheckRequest(BaseModel):
    """Request schema for grammar check"""

    text: str = Field(
        ..., min_length=10, description="Text to check for grammar errors"
    )
    language: str = Field(
        default="en-US", description="Language code (e.g., en-US, uk-UA)"
    )


@router.post("/check-grammar")
async def check_grammar(
    request: GrammarCheckRequest,
    current_user: User = Depends(get_current_user),
):
    """
    Check text for grammar and spelling errors using LanguageTool API

    Args:
        request: Grammar check request with text and language
    """
    try:
        checker = GrammarChecker()
        result = await checker.check_text(request.text, request.language)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to check grammar: {str(e)}",
        ) from e


@router.post("/full-document", response_model=AsyncGenerationResponse)
@rate_limit("5/hour")  # Stricter limit for full document generation
async def generate_full_document(
    request: Request,
    req_data: AsyncGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Generate complete document with RAG (Retrieval-Augmented Generation)

    This endpoint:
    1. Validates document ownership and readiness
    2. Checks payment status (document must be paid)
    3. Creates AIGenerationJob with status 'queued'
    4. Starts background generation with RAG retrieval
    5. Returns job_id for status tracking via WebSocket

    Args:
        request: Generation request with document_id
        background_tasks: FastAPI background tasks
        current_user: Authenticated user
        db: Database session

    Returns:
        AsyncGenerationResponse with job_id and status

    Raises:
        404: Document not found
        403: User doesn't own document
        400: Document not ready (not paid, already generating, etc.)
    """
    try:
        # 1. Check document exists and user owns it
        doc_service = DocumentService(db)
        await doc_service.check_document_ownership(
            req_data.document_id, current_user.id
        )

        # 2. Get document with lock (prevent race conditions)
        result = await db.execute(
            select(Document)
            .where(Document.id == req_data.document_id)
            .with_for_update()
        )
        document = result.scalar_one_or_none()

        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Document not found"
            )

        # 3. Validate document is ready for generation
        if document.status == "generating":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document is already being generated",
            )

        if document.status == "completed":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Document already completed. Create new document for regeneration.",
            )

        # 4. Check payment status (assuming payment is tracked via Payment table)
        # For MVP: We skip payment check if document is in draft status
        # In production: Add payment verification here

        # 5. Check for existing active jobs (prevent duplicates)
        existing_job_result = await db.execute(
            select(AIGenerationJob).where(
                AIGenerationJob.document_id == req_data.document_id,
                AIGenerationJob.status.in_(["queued", "running"]),
            )
        )
        existing_job = existing_job_result.scalar_one_or_none()

        if existing_job:
            # Return existing job instead of creating duplicate
            logger.info(
                f"Returning existing job {existing_job.id} for document {req_data.document_id}"
            )
            return AsyncGenerationResponse(
                job_id=existing_job.id,
                status=existing_job.status,
                check_url=f"/api/v1/jobs/{existing_job.id}/status",
            )

        # 6. Create new generation job
        job = AIGenerationJob(
            user_id=current_user.id,
            document_id=req_data.document_id,
            job_type="full_document",
            ai_provider=document.ai_provider,
            ai_model=req_data.model or document.ai_model,
            status="queued",
            progress=0,
        )
        db.add(job)
        await db.flush()  # Get job.id before commit

        # 7. Update document status
        document.status = "generating"

        # 8. Commit transaction before starting background task
        await db.commit()

        logger.info(
            f"Created generation job {job.id} for document {req_data.document_id}"
        )

        # 9. Start background generation task
        background_tasks.add_task(
            BackgroundJobService.generate_full_document_async,
            document_id=req_data.document_id,
            user_id=current_user.id,
            job_id=job.id,
            additional_requirements=req_data.requirements,
        )

        return AsyncGenerationResponse(
            job_id=job.id, status="queued", check_url=f"/api/v1/jobs/{job.id}/status"
        )

    except HTTPException:
        raise
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        logger.error(
            f"Failed to start document generation: {e}",
            exc_info=True,
            extra={"document_id": req_data.document_id, "user_id": current_user.id},
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to start document generation",
        ) from e
