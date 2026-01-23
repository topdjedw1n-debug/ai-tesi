"""
Job status and async generation endpoints
"""
import logging

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user, get_current_user_ws
from app.core.exceptions import NotFoundError
from app.models.auth import User
from app.schemas.document import (
    AsyncGenerationRequest,
    AsyncGenerationResponse,
    JobStatusResponse,
)
from app.services.background_jobs import BackgroundJobService
from app.services.document_service import DocumentService
from app.services.websocket_manager import manager

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/generate/document-async", response_model=AsyncGenerationResponse)
async def generate_document_async(
    request: AsyncGenerationRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> AsyncGenerationResponse:
    """
    Start async document generation.
    Returns immediately with job_id for status checking.
    """
    try:
        # Verify document exists and belongs to user
        document_service = DocumentService(db)
        document = await document_service.check_document_ownership(
            request.document_id, int(current_user.id)
        )

        # Create job in database
        from app.models.document import AIGenerationJob

        job = AIGenerationJob(
            document_id=document.id,
            user_id=int(current_user.id),
            job_type="document_generation",
            status="queued",
            progress=0,
            ai_model=request.model,
        )
        db.add(job)
        await db.flush()  # Get job.id
        await db.commit()

        # Start background task
        background_tasks.add_task(
            BackgroundJobService.generate_full_document_async,
            document.id,
            current_user.id,
            job.id,
            request.requirements,
        )

        return AsyncGenerationResponse(
            job_id=int(job.id),
            status="queued",
            check_url=f"/api/v1/jobs/{job.id}/status",
        )
    except NotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e)) from e
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start document generation: {str(e)}",
        ) from e


@router.get("/{job_id}/status", response_model=JobStatusResponse)
async def get_job_status(
    job_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse:
    """
    Get status of a background job.
    """
    try:
        from app.models.document import AIGenerationJob

        # Get job
        result = await db.execute(
            select(AIGenerationJob).where(
                AIGenerationJob.id == job_id, AIGenerationJob.user_id == current_user.id
            )
        )
        job = result.scalar_one_or_none()

        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Job not found"
            )

        return JobStatusResponse(
            job_id=job_id,
            status=str(job.status),
            progress=int(job.progress),
            document_id=int(job.document_id) if job.document_id else None,
            error_message=str(job.error_message) if job.error_message else None,
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get job status: {str(e)}",
        ) from e


@router.websocket("/ws/generation/{document_id}")
async def generation_progress_ws(
    websocket: WebSocket,
    document_id: int,
    current_user: User = Depends(get_current_user_ws),
) -> None:
    """
    WebSocket endpoint for real-time document generation progress updates.

    Connects to receive progress updates as document is being generated.
    """
    # Verify document ownership
    from app.core.database import AsyncSessionLocal

    async with AsyncSessionLocal() as db:
        document_service = DocumentService(db)
        await document_service.check_document_ownership(
            document_id, int(current_user.id)
        )

    # Connect to WebSocket manager
    await manager.connect(websocket, int(current_user.id))

    try:
        # Keep connection alive and wait for messages
        while True:
            # Client can send ping to check connection
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket, int(current_user.id))
        logger.info(f"WebSocket disconnected for user {current_user.id}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket, int(current_user.id))
