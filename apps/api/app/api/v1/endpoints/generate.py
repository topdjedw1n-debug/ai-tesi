"""
AI generation endpoints
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.schemas.document import (
    OutlineRequest,
    OutlineResponse,
    SectionRequest,
    SectionResponse
)
from app.services.ai_service import AIService
from app.core.exceptions import NotFoundError, AIProviderError

router = APIRouter()


@router.post("/outline", response_model=OutlineResponse)
async def generate_outline(
    request: OutlineRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate document outline using AI"""
    try:
        # TODO: Get current user from authentication
        user_id = 1  # Placeholder
        
        ai_service = AIService(db)
        result = await ai_service.generate_outline(
            document_id=request.document_id,
            user_id=user_id,
            additional_requirements=request.additional_requirements
        )
        return result
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AIProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate outline"
        )


@router.post("/section", response_model=SectionResponse)
async def generate_section(
    request: SectionRequest,
    db: AsyncSession = Depends(get_db)
):
    """Generate a specific section using AI"""
    try:
        # TODO: Get current user from authentication
        user_id = 1  # Placeholder
        
        ai_service = AIService(db)
        result = await ai_service.generate_section(
            document_id=request.document_id,
            section_title=request.section_title,
            section_index=request.section_index,
            user_id=user_id,
            additional_requirements=request.additional_requirements
        )
        return result
    except NotFoundError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except AIProviderError as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate section"
        )


@router.get("/models")
async def list_available_models():
    """List available AI models"""
    return {
        "openai": [
            {"id": "gpt-4", "name": "GPT-4", "max_tokens": 4000},
            {"id": "gpt-4-turbo", "name": "GPT-4 Turbo", "max_tokens": 8000},
            {"id": "gpt-3.5-turbo", "name": "GPT-3.5 Turbo", "max_tokens": 4000}
        ],
        "anthropic": [
            {"id": "claude-3-5-sonnet-20241022", "name": "Claude 3.5 Sonnet", "max_tokens": 4000},
            {"id": "claude-3-opus-20240229", "name": "Claude 3 Opus", "max_tokens": 4000}
        ]
    }


@router.get("/usage/{user_id}")
async def get_user_usage(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Get AI usage statistics for a user"""
    try:
        ai_service = AIService(db)
        result = await ai_service.get_user_usage(user_id)
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to get usage statistics"
        )
