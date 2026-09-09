"""
Job status and async generation endpoints
"""

import logging
from datetime import UTC, datetime
from typing import cast

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
from app.models.document import AIGenerationJob
from app.schemas.document import (
    AsyncGenerationRequest,
    AsyncGenerationResponse,
    JobStatusResponse,
)
from app.services.document_service import DocumentService
from app.services.executor_v2.warnings import is_v2, status_fields
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
    from app.api.v1.endpoints.generate import enqueue_full_document

    # Compatibility URL shares the same confirmation, duplicate and durable queue boundary.
    return await enqueue_full_document(request, current_user, db)


@router.get("/document/{document_id}/status", response_model=JobStatusResponse | None)
async def get_document_job_status(
    document_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> JobStatusResponse | None:
    """Restore the latest full-document state after reload or a dropped socket."""
    try:
        await DocumentService(db).check_document_ownership(
            document_id, int(current_user.id)
        )
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail="Document not found") from error
    job = (
        await db.execute(
            select(AIGenerationJob)
            .where(
                AIGenerationJob.document_id == document_id,
                AIGenerationJob.user_id == int(current_user.id),
                AIGenerationJob.job_type == "full_document",
            )
            .order_by(AIGenerationJob.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if job is None:
        return None
    from app.models.document import Document, ProductionCase
    from app.services.generation_recovery import recovery_state

    document = await db.get(Document, document_id)
    case = (
        await db.execute(
            select(ProductionCase).where(ProductionCase.document_id == document_id)
        )
    ).scalar_one_or_none()
    recovery = await recovery_state(db, document, job, case)
    from app.services.generation_operations import journal_usage

    confirmed, unknown = await journal_usage(db, document_id, int(job.id))
    recovery["usage"] = {
        "confirmed_tokens": max(int(job.total_tokens or 0), confirmed.total_tokens),
        "recorded_cost_cents": max(
            int(job.cost_cents or 0), confirmed.cost_usd_cents()
        ),
        "unknown_provider_attempts": unknown,
    }

    return JobStatusResponse(
        job_id=int(job.id),
        document_id=document_id,
        status=str(job.status),
        progress=int(job.progress or 0),
        error_message=str(job.error_message) if job.error_message else None,
        attempt_count=int(job.attempt_count or 0),
        max_attempts=int(job.max_attempts or 0),
        recovery=recovery,
        started_at=cast(datetime | None, job.started_at),
        available_at=cast(datetime | None, job.available_at),
        heartbeat_at=cast(datetime | None, job.heartbeat_at),
        lease_expires_at=cast(datetime | None, job.lease_expires_at),
        observed_at=datetime.now(UTC),
        **{
            **status_fields(job),
            **(
                {
                    "tokens_so_far": recovery["usage"]["confirmed_tokens"],
                    "cost_cents_so_far": recovery["usage"]["recorded_cost_cents"],
                }
                if is_v2(job)
                else {}
            ),
        },
    )


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

        if job.job_type == "full_document" and job.document_id:
            projected = await get_document_job_status(
                int(job.document_id), current_user, db
            )
            if projected and projected.job_id == job_id:
                return projected
        return JobStatusResponse(
            **status_fields(job),
            observed_at=datetime.now(UTC),
            started_at=job.started_at,
            heartbeat_at=job.heartbeat_at,
            attempt_count=int(job.attempt_count or 0),
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
