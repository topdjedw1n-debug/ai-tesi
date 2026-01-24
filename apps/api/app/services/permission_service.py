"""
Permission service for checking and managing admin permissions
"""

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions import AdminPermissions
from app.models.admin import AdminPermission


async def check_user_permission(
    db: AsyncSession,
    user_id: int,
    permission: str | AdminPermissions,
) -> bool:
    """
    Check if user has a specific permission.

    Args:
        db: Database session
        user_id: User ID to check
        permission: Permission to check (string or AdminPermissions enum)

    Returns:
        True if user has permission, False otherwise
    """
    # Convert enum to string if needed
    permission_str = (
        permission.value if isinstance(permission, AdminPermissions) else permission
    )

    # Query for active permission
    query = select(AdminPermission).where(
        and_(
            AdminPermission.user_id == user_id,
            AdminPermission.permission == permission_str,
            AdminPermission.revoked_at.is_(None),  # Permission not revoked
        )
    )

    result = await db.execute(query)
    permission_obj = result.scalar_one_or_none()

    return permission_obj is not None


async def get_user_permissions(db: AsyncSession, user_id: int) -> list[str]:
    """
    Get all active permissions for a user.

    Args:
        db: Database session
        user_id: User ID

    Returns:
        List of permission strings
    """
    query = select(AdminPermission.permission).where(
        and_(
            AdminPermission.user_id == user_id,
            AdminPermission.revoked_at.is_(None),  # Only active permissions
        )
    )

    result = await db.execute(query)
    permissions = result.scalars().all()

    return list(permissions)


async def grant_permission(
    db: AsyncSession,
    user_id: int,
    permission: str | AdminPermissions,
    granted_by: int,
) -> AdminPermission:
    """
    Grant a permission to a user.

    Args:
        db: Database session
        user_id: User ID to grant permission to
        permission: Permission to grant
        granted_by: User ID who is granting the permission (admin)

    Returns:
        AdminPermission object
    """
    from app.models.auth import User

    # Convert enum to string if needed
    permission_str = (
        permission.value if isinstance(permission, AdminPermissions) else permission
    )

    # Check if permission already exists and is active
    existing = await db.execute(
        select(AdminPermission).where(
            and_(
                AdminPermission.user_id == user_id,
                AdminPermission.permission == permission_str,
                AdminPermission.revoked_at.is_(None),
            )
        )
    )
    if existing.scalar_one_or_none():
        raise ValueError(
            f"Permission {permission_str} already granted to user {user_id}"
        )

    # Verify grantor is admin
    grantor = await db.get(User, granted_by)
    if not grantor or not grantor.is_admin:
        raise ValueError("Only admins can grant permissions")

    # Create new permission
    admin_permission = AdminPermission(
        user_id=user_id,
        permission=permission_str,
        granted_by=granted_by,
    )

    db.add(admin_permission)
    await db.commit()
    await db.refresh(admin_permission)

    return admin_permission


async def revoke_permission(
    db: AsyncSession,
    permission_id: int,
    revoked_by: int,
) -> AdminPermission:
    """
    Revoke a permission from a user.

    Args:
        db: Database session
        permission_id: Permission ID to revoke
        revoked_by: User ID who is revoking the permission (admin)

    Returns:
        Updated AdminPermission object
    """
    from datetime import datetime

    from app.models.auth import User

    # Get permission
    permission = await db.get(AdminPermission, permission_id)
    if not permission:
        raise ValueError(f"Permission {permission_id} not found")

    # Check if already revoked
    if permission.revoked_at is not None:
        raise ValueError(f"Permission {permission_id} already revoked")

    # Verify revoker is admin
    revoker = await db.get(User, revoked_by)
    if not revoker:
        raise ValueError("Revoker not found")
    if not revoker.is_admin:
        raise ValueError("Only admins can revoke permissions")

    # Revoke permission
    permission.revoked_at = datetime.utcnow()
    permission.revoked_by = revoked_by

    await db.commit()
    await db.refresh(permission)

    return permission
