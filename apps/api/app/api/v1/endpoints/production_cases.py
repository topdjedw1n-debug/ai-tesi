"""Admin production case endpoints for the QA-first workflow."""

from typing import Any
from urllib.parse import quote

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.dependencies import require_permission
from app.core.permissions import AdminPermissions
from app.core.production_access import (
    require_owned_document,
    require_production_permission,
)
from app.models.auth import User
from app.schemas.production import (
    ContentReviewRequest,
    DetectorReportResponse,
    EditorTaskCreate,
    EditorTaskResponse,
    GateOverrideRequest,
    ManualDetectorResultRequest,
    ProductionCaseCreate,
    ProductionCaseListResponse,
    ProductionCaseResponse,
    ProductionCaseUpdate,
    ReleaseGateResponse,
    ReleaseRequest,
)
from app.services.production_case_service import (
    EditorTaskService,
    ProductionCaseService,
)
from app.services.release_policy import MAX_REPORT_BYTES

router = APIRouter()


def check_operator_assignments(
    user: User, payload: ProductionCaseCreate | ProductionCaseUpdate
) -> None:
    if not user.is_admin and (
        payload.manager_id not in (None, int(user.id)) or payload.editor_id is not None
    ):
        raise HTTPException(
            status_code=403, detail="Operator cannot assign other users"
        )


@router.get("", response_model=ProductionCaseListResponse)
async def list_production_cases(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    release_status: str | None = None,
    manager_id: int | None = Query(None, gt=0),
    editor_id: int | None = Query(None, gt=0),
    current_user: User = Depends(
        require_production_permission(AdminPermissions.VIEW_DOCUMENTS)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """List production cases for internal managers/admins."""
    service = ProductionCaseService(db)
    return await service.list_cases(
        page=page,
        per_page=per_page,
        release_status=release_status,
        manager_id=manager_id,
        editor_id=editor_id,
        owner_user_id=None if current_user.is_admin else int(current_user.id),
    )


@router.post(
    "",
    response_model=ProductionCaseResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_production_case(
    payload: ProductionCaseCreate,
    current_user: User = Depends(
        require_production_permission(AdminPermissions.MANAGE_PRODUCTION_CASES)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a production case around an existing document without payment."""
    await require_owned_document(db, current_user, payload.document_id)
    check_operator_assignments(current_user, payload)
    service = ProductionCaseService(db)
    production_case = await service.create_case(payload, actor_id=int(current_user.id))
    return await service.serialize_case(production_case)


@router.get("/{case_id}", response_model=ProductionCaseResponse)
async def get_production_case(
    case_id: int,
    current_user: User = Depends(
        require_production_permission(AdminPermissions.VIEW_DOCUMENTS)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get one production case with linked document and assignee context."""
    service = ProductionCaseService(db)
    production_case = await service.get_case(case_id)
    return await service.serialize_case(production_case)


@router.patch("/{case_id}", response_model=ProductionCaseResponse)
async def update_production_case(
    case_id: int,
    payload: ProductionCaseUpdate,
    current_user: User = Depends(
        require_production_permission(AdminPermissions.MANAGE_PRODUCTION_CASES)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Patch production case assignment, metadata, and separate status dimensions."""
    check_operator_assignments(current_user, payload)
    if not current_user.is_admin and payload.model_fields_set - {
        "manager_id",
        "editor_id",
        "deadline_at",
        "citation_style",
        "requirements_text",
        "release_notes",
    }:
        raise HTTPException(
            status_code=403,
            detail="Operator cannot change administrative statuses or costs",
        )
    service = ProductionCaseService(db)
    production_case = await service.update_case(
        case_id,
        payload,
        actor_id=int(current_user.id),
    )
    return await service.serialize_case(production_case)


@router.get("/{case_id}/release-gates", response_model=list[ReleaseGateResponse])
async def get_release_gates(
    case_id: int,
    current_user: User = Depends(
        require_production_permission(AdminPermissions.VIEW_DOCUMENTS)
    ),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Return computed release gates without duplicating provenance evidence."""
    return await ProductionCaseService(db).get_release_gates(case_id)


@router.post(
    "/{case_id}/release-gates/{gate_key}/override",
    response_model=ReleaseGateResponse,
)
async def override_release_gate(
    case_id: int,
    gate_key: str,
    payload: GateOverrideRequest,
    current_user: User = Depends(
        require_permission(AdminPermissions.MANAGE_PRODUCTION_CASES)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Override an allowed release gate with an audited reason."""
    return await ProductionCaseService(db).override_gate(
        case_id,
        gate_key,
        payload.reason,
        actor_id=int(current_user.id),
    )


@router.post(
    "/{case_id}/release-gates/{gate_key}/detector-result",
    response_model=ReleaseGateResponse,
)
async def record_detector_result(
    case_id: int,
    gate_key: str,
    payload: ManualDetectorResultRequest,
    current_user: User = Depends(
        require_production_permission(AdminPermissions.RELEASE_DOCUMENTS)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Record a release-manager decision for a current detector artifact."""
    return await ProductionCaseService(db).record_detector_result(
        case_id,
        gate_key,
        payload,
        actor_id=int(current_user.id),
    )


@router.post(
    "/{case_id}/detector-reports",
    response_model=DetectorReportResponse,
    status_code=status.HTTP_201_CREATED,
)
async def upload_detector_report(
    case_id: int,
    artifact_fingerprint_sha256: str = Form(pattern=r"^[a-f0-9]{64}$"),
    file: UploadFile = File(),
    current_user: User = Depends(
        require_production_permission(AdminPermissions.RELEASE_DOCUMENTS)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    content = await file.read(MAX_REPORT_BYTES + 1)
    return await ProductionCaseService(db).upload_detector_report(
        case_id,
        artifact_fingerprint_sha256,
        file.filename or "Compilatio",
        content,
        int(current_user.id),
    )


@router.get("/{case_id}/detector-reports", response_model=list[DetectorReportResponse])
async def list_detector_reports(
    case_id: int,
    current_user: User = Depends(
        require_production_permission(AdminPermissions.VIEW_DOCUMENTS)
    ),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    return await ProductionCaseService(db).list_detector_reports(case_id)


@router.get("/{case_id}/detector-reports/{report_id}/file")
async def download_detector_report(
    case_id: int,
    report_id: int,
    current_user: User = Depends(
        require_production_permission(AdminPermissions.VIEW_DOCUMENTS)
    ),
    db: AsyncSession = Depends(get_db),
) -> Response:
    evidence, content = await ProductionCaseService(db).download_detector_report(
        case_id, report_id
    )
    return Response(
        content,
        media_type=evidence["content_type"],
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(evidence['filename'], safe='')}",
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.post("/{case_id}/content-review", response_model=ReleaseGateResponse)
async def record_content_review(
    case_id: int,
    payload: ContentReviewRequest,
    current_user: User = Depends(
        require_production_permission(AdminPermissions.RELEASE_DOCUMENTS)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    return await ProductionCaseService(db).record_content_review(
        case_id, payload, int(current_user.id)
    )


@router.post("/{case_id}/release", response_model=ProductionCaseResponse)
async def release_production_case(
    case_id: int,
    payload: ReleaseRequest,
    current_user: User = Depends(
        require_production_permission(AdminPermissions.RELEASE_DOCUMENTS)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Release a case only when all blocking gates are resolved."""
    service = ProductionCaseService(db)
    production_case = await service.release_case(
        case_id,
        actor_id=int(current_user.id),
        notes=payload.notes,
    )
    return await service.serialize_case(production_case)


@router.post("/{case_id}/editor-tasks", response_model=EditorTaskResponse)
async def create_editor_task(
    case_id: int,
    payload: EditorTaskCreate,
    current_user: User = Depends(
        require_permission(AdminPermissions.MANAGE_PRODUCTION_CASES)
    ),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create an editor task tied to a case and source finding."""
    data = payload.model_copy(update={"production_case_id": case_id})
    service = EditorTaskService(db)
    task = await service.create_task(data, actor_id=int(current_user.id))
    return await service.serialize_task(task)
