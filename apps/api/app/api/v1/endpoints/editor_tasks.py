"""Editor workspace endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.models.auth import User
from app.schemas.production import (
    EditorTaskListResponse,
    EditorTaskResolveRequest,
    EditorTaskResponse,
    EditorTaskUpdate,
)
from app.services.production_case_service import EditorTaskService

router = APIRouter()


@router.get("/tasks", response_model=EditorTaskListResponse)
async def list_editor_tasks(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    status: str | None = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """List assigned editor tasks; admins can see all tasks."""
    return await EditorTaskService(db).list_tasks(
        user=current_user,
        page=page,
        per_page=per_page,
        status_filter=status,
    )


@router.get("/tasks/{task_id}", response_model=EditorTaskResponse)
async def get_editor_task(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get one editor task if assigned to the current editor."""
    service = EditorTaskService(db)
    task = await service.get_task(task_id, current_user)
    return await service.serialize_task(task)


@router.patch("/tasks/{task_id}", response_model=EditorTaskResponse)
async def update_editor_task(
    task_id: int,
    data: EditorTaskUpdate,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Update editor task state without exposing unrelated admin surfaces."""
    service = EditorTaskService(db)
    task = await service.update_task(task_id, data, current_user)
    return await service.serialize_task(task)


@router.post("/tasks/{task_id}/resolve", response_model=EditorTaskResponse)
async def resolve_editor_task(
    task_id: int,
    data: EditorTaskResolveRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Resolve or reject an assigned editor task with minutes spent."""
    service = EditorTaskService(db)
    task = await service.resolve_task(task_id, data, current_user)
    return await service.serialize_task(task)
