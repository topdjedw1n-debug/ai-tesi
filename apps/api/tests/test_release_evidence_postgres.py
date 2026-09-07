"""Real row-lock races. Set M0_03_TEST_DATABASE_URL to an isolated PostgreSQL DB."""

import asyncio
import os
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.schema import CreateSchema, DropSchema

from app.core import database
from app.core.database import AsyncSessionLocal, Base
from app.models.document import ProductionCase
from app.schemas.production import ContentReviewRequest
from app.services.production_case_service import ProductionCaseService
from tests import test_production_cases as case_fixtures
from tests import test_release_evidence as evidence_fixtures

client = case_fixtures.client
_stable_artifact_storage = case_fixtures._stable_artifact_storage
pytestmark = pytest.mark.asyncio


@pytest.fixture
async def postgres():
    url = os.environ.get("M0_03_TEST_DATABASE_URL")
    if not url:
        pytest.skip(
            "An isolated PostgreSQL database is required for the row-lock races"
        )
    schema = f"m003_{uuid4().hex}"
    bootstrap = create_async_engine(url)
    async with bootstrap.begin() as connection:
        await connection.execute(CreateSchema(schema))
    engine = create_async_engine(
        url, connect_args={"server_settings": {"search_path": schema}}
    )
    original_engine = database._engine
    original_bind = AsyncSessionLocal.kw["bind"]
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        database._engine = engine
        AsyncSessionLocal.configure(bind=engine)
        yield engine
    finally:
        AsyncSessionLocal.configure(bind=original_bind)
        database._engine = original_engine
        await engine.dispose()
        async with bootstrap.begin() as connection:
            await connection.execute(DropSchema(schema, cascade=True))
        await bootstrap.dispose()


@pytest.fixture
async def pg_work(postgres, client, monkeypatch, _stable_artifact_storage):
    return await evidence_fixtures.make_work(
        client, monkeypatch, _stable_artifact_storage
    )


@pytest.mark.parametrize("first_action", ["release", "rewritten"])
async def test_release_and_negative_review_serialize_on_document_lock(
    postgres, pg_work, client, first_action
):
    admin, _, case = pg_work
    await evidence_fixtures.ready(client, pg_work)
    held = asyncio.Event()
    proceed = asyncio.Event()
    review = ContentReviewRequest(
        artifact_fingerprint_sha256=case["document"]["artifact_bindings"]["docx"][
            "fingerprint_sha256"
        ],
        decision="rewritten",
        reason="A human needed to rewrite this generated content.",
    )

    async def action(name, first):
        async with AsyncSessionLocal() as db:
            if not first:
                await db.execute(text("SET LOCAL application_name = 'm003-contender'"))
            service = ProductionCaseService(db)
            if first:
                await service.get_case_and_document_for_update(case["id"])
                held.set()
                await proceed.wait()
            try:
                if name == "release":
                    await service.release_case(case["id"], int(admin.id))
                else:
                    await service.record_content_review(
                        case["id"], review, int(admin.id)
                    )
                return 200
            except HTTPException as error:
                return error.status_code

    first = asyncio.create_task(action(first_action, True))
    second = None
    try:
        await asyncio.wait_for(held.wait(), timeout=5)
        second_action = "rewritten" if first_action == "release" else "release"
        second = asyncio.create_task(action(second_action, False))

        async def observe_real_lock_wait():
            while True:
                if second.done():
                    pytest.fail(f"Contender bypassed document lock: {await second}")
                async with postgres.connect() as connection:
                    waiting = await connection.scalar(
                        text(
                            "SELECT count(*) FROM pg_stat_activity WHERE "
                            "application_name = 'm003-contender' AND wait_event_type = 'Lock'"
                        )
                    )
                if waiting:
                    return
                await asyncio.sleep(0.01)

        await asyncio.wait_for(observe_real_lock_wait(), timeout=5)
        proceed.set()
        outcomes = await asyncio.wait_for(asyncio.gather(first, second), timeout=10)
        assert outcomes == ([200, 200] if first_action == "release" else [200, 409])
        async with AsyncSessionLocal() as db:
            final = await db.get(ProductionCase, case["id"])
            assert final.release_status != "released"
            assert final.released_docx_path is None
            gates = await ProductionCaseService(db).get_release_gates(case["id"])
            assert (
                next(gate for gate in gates if gate["gate_key"] == "editorial_review")[
                    "status"
                ]
                == "failed"
            )
    finally:
        proceed.set()
        for task in (first, second):
            if task and not task.done():
                task.cancel()
        await asyncio.gather(
            *(task for task in (first, second) if task), return_exceptions=True
        )
