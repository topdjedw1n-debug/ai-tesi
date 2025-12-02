"""
Settings management endpoints
"""

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.dependencies import get_db, require_permission
from app.core.permissions import AdminPermissions
from app.models.auth import User
from app.schemas.settings import (
    AISettingsUpdate,
    LimitSettingsUpdate,
    MaintenanceSettingsUpdate,
    PricingSettingsUpdate,
    SettingHistoryResponse,
)
from app.services.admin_service import AdminService
from app.services.settings_service import SettingsService

router = APIRouter()


@router.get("", response_model=dict[str, dict[str, Any]])
async def get_all_settings(
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get all system settings grouped by category.

    Requires: VIEW_SETTINGS permission
    """
    try:
        service = SettingsService(db)
        settings = await service.get_settings()
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings: {str(e)}",
        ) from e


@router.get("/{category}", response_model=dict[str, Any])
async def get_settings_by_category(
    category: str,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get settings for a specific category.

    Categories: pricing, ai, limits, maintenance

    Requires: VIEW_SETTINGS permission
    """
    try:
        service = SettingsService(db)
        settings = await service.get_settings_by_category(category)
        return settings
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get settings for category {category}: {str(e)}",
        ) from e


@router.put("/pricing", response_model=dict[str, Any])
async def update_pricing_settings(
    settings: PricingSettingsUpdate,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.CHANGE_PRICING)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update pricing settings.

    Requires: CHANGE_PRICING permission (critical action)

    This action is logged in audit logs.
    """
    try:
        service = SettingsService(db)
        admin_service = AdminService(db)

        # Get old values for audit log
        old_settings = await service.get_pricing_settings()

        # Prepare settings dict for update
        settings_dict = {
            "pricing.price_per_page": float(settings.price_per_page),
            "pricing.min_pages": settings.min_pages,
            "pricing.max_pages": settings.max_pages,
            "pricing.currencies": settings.currencies,
        }

        # Update settings
        updated = await service.update_pricing_settings(settings_dict, current_user.id)

        # Audit log
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action="change_pricing",
            target_type="settings",
            target_id=None,
            old_value=old_settings,
            new_value={k: v.value for k, v in updated.items()},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            correlation_id=request.headers.get("X-Request-ID"),
        )

        await db.commit()

        # Return updated settings
        return {k: v.value for k, v in updated.items()}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update pricing settings: {str(e)}",
        ) from e


@router.put("/ai", response_model=dict[str, Any])
async def update_ai_settings(
    settings: AISettingsUpdate,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.CHANGE_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update AI settings.

    Requires: CHANGE_SETTINGS permission
    """
    try:
        service = SettingsService(db)
        admin_service = AdminService(db)

        # Get old values for audit log
        old_settings = await service.get_ai_settings()

        # Prepare settings dict for update
        settings_dict = {
            "ai.default_provider": settings.default_provider,
            "ai.default_model": settings.default_model,
            "ai.fallback_models": settings.fallback_models,
            "ai.max_retries": settings.max_retries,
            "ai.timeout_seconds": settings.timeout_seconds,
            "ai.temperature_default": settings.temperature_default,
        }

        # Update settings
        updated = await service.update_ai_settings(settings_dict, current_user.id)

        # Audit log
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action="update_ai_settings",
            target_type="settings",
            target_id=None,
            old_value=old_settings,
            new_value={k: v.value for k, v in updated.items()},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            correlation_id=request.headers.get("X-Request-ID"),
        )

        await db.commit()

        # Return updated settings
        return {k: v.value for k, v in updated.items()}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update AI settings: {str(e)}",
        ) from e


@router.put("/limits", response_model=dict[str, Any])
async def update_limit_settings(
    settings: LimitSettingsUpdate,
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.CHANGE_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update limit settings.

    Requires: CHANGE_SETTINGS permission
    """
    try:
        service = SettingsService(db)
        admin_service = AdminService(db)

        # Get old values for audit log
        old_settings = await service.get_limit_settings()

        # Prepare settings dict for update
        settings_dict = {
            "limits.max_concurrent_generations": settings.max_concurrent_generations,
            "limits.max_documents_per_user": settings.max_documents_per_user,
            "limits.max_pages_per_document": settings.max_pages_per_document,
            "limits.daily_token_limit": settings.daily_token_limit,
        }

        # Update settings
        updated = await service.update_limit_settings(settings_dict, current_user.id)

        # Audit log
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action="update_limit_settings",
            target_type="settings",
            target_id=None,
            old_value=old_settings,
            new_value={k: v.value for k, v in updated.items()},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            correlation_id=request.headers.get("X-Request-ID"),
        )

        await db.commit()

        # Return updated settings
        return {k: v.value for k, v in updated.items()}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update limit settings: {str(e)}",
        ) from e


@router.put("/maintenance", response_model=dict[str, Any])
async def update_maintenance_settings(
    settings: MaintenanceSettingsUpdate,
    request: Request,
    current_user: User = Depends(
        require_permission(AdminPermissions.SYSTEM_MAINTENANCE)
    ),
    db: AsyncSession = Depends(get_db),
):
    """
    Update maintenance mode settings.

    Requires: SYSTEM_MAINTENANCE permission (critical action)

    This action is logged in audit logs.
    """
    try:
        service = SettingsService(db)
        admin_service = AdminService(db)

        # Get old values for audit log
        old_settings = await service.get_maintenance_settings()

        # Prepare settings dict for update
        settings_dict: dict[str, Any] = {
            "maintenance.enabled": settings.enabled,
            "maintenance.message": settings.message,
            "maintenance.allowed_ips": settings.allowed_ips,
        }

        if settings.estimated_end_time:
            settings_dict[
                "maintenance.estimated_end_time"
            ] = settings.estimated_end_time.isoformat()

        # Update settings
        updated = await service.update_maintenance_settings(
            settings_dict, current_user.id
        )

        # Audit log (critical action)
        action = "enable_maintenance" if settings.enabled else "disable_maintenance"
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action=action,
            target_type="settings",
            target_id=None,
            old_value=old_settings,
            new_value={k: v.value for k, v in updated.items()},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            correlation_id=request.headers.get("X-Request-ID"),
        )

        await db.commit()

        # Return updated settings
        return {k: v.value for k, v in updated.items()}
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update maintenance settings: {str(e)}",
        ) from e


@router.put("/{category}", response_model=dict[str, Any])
async def update_settings_category(
    category: str,
    settings: dict[str, Any],
    request: Request,
    current_user: User = Depends(require_permission(AdminPermissions.CHANGE_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Update settings for a specific category (generic endpoint).

    Requires: CHANGE_SETTINGS permission

    Note: For pricing and maintenance, use specific endpoints as they require
    different permissions.
    """
    try:
        # Prevent using generic endpoint for critical categories
        if category in ["pricing", "maintenance"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Use specific endpoint for {category} settings",
            )

        service = SettingsService(db)
        admin_service = AdminService(db)

        # Get old values for audit log
        old_settings = await service.get_settings_by_category(category)

        # Update settings
        updated = await service.update_settings(category, settings, current_user.id)

        # Audit log
        await admin_service.log_admin_action(
            admin_id=current_user.id,
            action=f"update_{category}_settings",
            target_type="settings",
            target_id=None,
            old_value=old_settings,
            new_value={k: v.value for k, v in updated.items()},
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("User-Agent"),
            correlation_id=request.headers.get("X-Request-ID"),
        )

        await db.commit()

        # Return updated settings
        return {k: v.value for k, v in updated.items()}
    except HTTPException:
        raise
    except Exception as e:
        await db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update {category} settings: {str(e)}",
        ) from e


@router.get("/history/{key}", response_model=SettingHistoryResponse)
async def get_setting_history(
    key: str,
    current_user: User = Depends(require_permission(AdminPermissions.VIEW_SETTINGS)),
    db: AsyncSession = Depends(get_db),
):
    """
    Get history of changes for a specific setting.

    Requires: VIEW_SETTINGS permission
    """
    try:
        service = SettingsService(db)
        history = await service.get_setting_history(key)

        return SettingHistoryResponse(
            key=key,
            history=history,
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get history for setting {key}: {str(e)}",
        ) from e

