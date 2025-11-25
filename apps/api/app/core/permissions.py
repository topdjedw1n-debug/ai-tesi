"""
Admin permissions system
"""

from enum import Enum


class AdminPermissions(str, Enum):
    """Granular permissions for admin users"""

    # Users
    VIEW_USERS = "view_users"
    EDIT_USERS = "edit_users"
    DELETE_USERS = "delete_users"
    BLOCK_USERS = "block_users"
    MAKE_ADMIN = "make_admin"

    # Documents
    VIEW_DOCUMENTS = "view_documents"
    DELETE_DOCUMENTS = "delete_documents"
    RETRY_DOCUMENTS = "retry_documents"

    # Payments
    VIEW_PAYMENTS = "view_payments"
    PROCESS_REFUNDS = "process_refunds"
    INITIATE_REFUNDS = "initiate_refunds"

    # Settings
    VIEW_SETTINGS = "view_settings"
    CHANGE_SETTINGS = "change_settings"
    CHANGE_PRICING = "change_pricing"

    # Analytics
    VIEW_ANALYTICS = "view_analytics"
    EXPORT_DATA = "export_data"

    # System
    VIEW_AUDIT_LOGS = "view_audit_logs"
    MANAGE_ADMINS = "manage_admins"
    SYSTEM_MAINTENANCE = "system_maintenance"

    # Super admin - має всі дозволи
    SUPER_ADMIN = "super_admin"

    def __str__(self) -> str:
        return self.value


def get_all_permissions() -> list[str]:
    """Get all available permissions as a list"""
    return [
        perm.value for perm in AdminPermissions if perm != AdminPermissions.SUPER_ADMIN
    ]
