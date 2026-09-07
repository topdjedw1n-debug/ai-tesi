"""Own-document production access without granting administration rights."""

from collections.abc import Callable

from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.dependencies import get_current_user, require_permission
from app.core.permissions import AdminPermissions
from app.models.auth import User
from app.models.document import Document, ProductionCase


async def require_owned_document(
    db: AsyncSession, user: User, document_id: int
) -> None:
    if user.is_admin:
        return
    document = await db.scalar(
        select(Document.id).where(
            Document.id == document_id, Document.user_id == user.id
        )
    )
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")


def require_production_permission(permission: AdminPermissions) -> Callable:
    """Keep existing admin permissions; admit configured owners on these routes.

    List and create routes must additionally scope their query/body document.
    Case/document IDs in route paths are checked centrally before any service
    can read evidence, mint a download token, or mutate a release decision.
    """
    if permission not in {
        AdminPermissions.VIEW_DOCUMENTS,
        AdminPermissions.MANAGE_PRODUCTION_CASES,
        AdminPermissions.RELEASE_DOCUMENTS,
    }:
        raise ValueError("Not a production permission")
    admin_check = require_permission(permission)

    async def check(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_admin:
            await admin_check(current_user=current_user, db=db)
            return current_user
        if int(current_user.id) not in settings.PRODUCTION_OPERATOR_USER_IDS:
            raise HTTPException(status_code=403, detail="Production access required")

        case_id = request.path_params.get("case_id")
        document_id = request.path_params.get("document_id")
        try:
            if case_id is not None:
                document_id = await db.scalar(
                    select(ProductionCase.document_id).where(
                        ProductionCase.id == int(case_id)
                    )
                )
                if document_id is None:
                    raise HTTPException(status_code=404, detail="Case not found")
            if document_id is not None:
                await require_owned_document(db, current_user, int(document_id))
        except ValueError as error:
            raise HTTPException(
                status_code=404, detail="Invalid production ID"
            ) from error
        return current_user

    return check
