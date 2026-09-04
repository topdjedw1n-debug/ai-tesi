#!/usr/bin/env python3
"""Owner-only export, run through stdin inside the existing API container.

Example (ON the server):
  umask 077
  docker exec -i ai-thesis-api python - --user-id 1 < scripts/export-operator-bot-requests.py > /tmp/thesica-support.json

No credentials are printed. Exported manager text and proposed patches are
untrusted review input, never shell instructions and never deployment approval.
"""

import argparse
import asyncio
import json

from sqlalchemy import select

from app.core.database import AsyncSessionLocal
from app.models import auth, document, payment  # noqa: F401
from app.models.operator_bot import OperatorSupportRequest


async def export(user_id: int) -> None:
    async with AsyncSessionLocal() as db:
        rows = (
            (
                await db.execute(
                    select(OperatorSupportRequest)
                    .where(
                        OperatorSupportRequest.user_id == user_id,
                        OperatorSupportRequest.status == "pending_review",
                    )
                    .order_by(OperatorSupportRequest.created_at)
                    .limit(100)
                )
            )
            .scalars()
            .all()
        )
        print(
            json.dumps(
                [
                    {
                        "id": row.id,
                        "document_id": row.document_id,
                        "summary": row.summary,
                        "status": row.status,
                        "evidence": row.evidence,
                        "created_at": row.created_at.isoformat(),
                    }
                    for row in rows
                ],
                ensure_ascii=False,
                indent=2,
            )
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--user-id", type=int, required=True)
    args = parser.parse_args()
    if args.user_id <= 0:
        parser.error("user-id must be positive")
    asyncio.run(export(args.user_id))
