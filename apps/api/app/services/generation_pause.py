"""Fail-closed transaction barrier shared by every supported paid start."""

from typing import Any

from fastapi import HTTPException
from sqlalchemy import select, text

from app.models.admin import SystemSetting

PAUSE_KEY = "generation.paused"
PAUSE_LOCK = 23709198609219394


async def lock_generation_pause(db: Any, *, shared: bool = False) -> None:
    if db.get_bind().dialect.name == "postgresql":
        await db.execute(
            text(
                "SELECT pg_advisory_xact_lock_shared(:key)"
                if shared
                else "SELECT pg_advisory_xact_lock(:key)"
            ),
            {"key": PAUSE_LOCK},
        )


async def require_generation_open(db: Any) -> None:
    try:
        await lock_generation_pause(db, shared=True)
        row = (
            await db.execute(
                select(SystemSetting)
                .where(SystemSetting.key == PAUSE_KEY)
                .execution_options(populate_existing=True)
            )
        ).scalar_one_or_none()
        if row is not None and row.value is not False:
            raise HTTPException(
                503,
                {
                    "reason_code": "generation_paused",
                    "message": "Нові запуски тимчасово зупинені. Збережений прогрес доступний.",
                },
            )
    except HTTPException:
        raise
    except Exception as error:
        raise HTTPException(
            503,
            {
                "reason_code": "generation_pause_unavailable",
                "message": "Стан дозволу на запуск недоступний.",
            },
        ) from error
