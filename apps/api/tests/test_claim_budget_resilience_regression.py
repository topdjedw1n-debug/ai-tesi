"""ISSUE-008: exhausted reservations must not expire the worker's document.

Found in production order 5/job 5 on 2026-09-07 and reproduced in isolated QA.
Report: .gstack/qa-reports/qa-report-localhost-2026-09-07.md
"""

import pytest

from app.services.generation_worker import (
    claim_next_generation_job,
    reserve_generation_claim_checks,
)
from tests import test_claim_verifier as claim_fixtures
from tests.test_generation_worker import _seed_job

mock_redis = claim_fixtures.mock_redis


@pytest.mark.asyncio
async def test_unlimited_claim_accounting_survives_more_than_old_cap(db_session):
    document, job = await _seed_job(db_session, email="unlimited-claims@example.com")
    claimed = await claim_next_generation_job(
        db_session, worker_id="qa", lease_seconds=120
    )
    args = {
        "job_id": job.id,
        "document_id": document.id,
        "worker_id": claimed.lease_owner,
        "lease_token": claimed.lease_token,
        "max_checks": None,
    }
    assert await reserve_generation_claim_checks(db_session, requested=100, **args) == (
        100,
        100,
    )
    assert await reserve_generation_claim_checks(db_session, requested=32, **args) == (
        32,
        132,
    )
    await db_session.refresh(job)
    assert job.claim_checks_used == 132


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", [0, 1])
async def test_empty_claim_reservation_keeps_loaded_document_usable(
    db_session, requested
):
    document, job = await _seed_job(db_session, email="claim-budget-qa@example.com")
    claimed = await claim_next_generation_job(
        db_session, worker_id="qa", lease_seconds=120
    )
    args = {
        "job_id": job.id,
        "document_id": document.id,
        "worker_id": claimed.lease_owner,
        "lease_token": claimed.lease_token,
        "max_checks": 1,
    }
    provider = document.ai_provider
    assert await reserve_generation_claim_checks(db_session, requested=1, **args) == (
        1,
        1,
    )
    assert await reserve_generation_claim_checks(
        db_session, requested=requested, **args
    ) == (0, 1)
    # The next section attempt reads these already-loaded fields synchronously.
    assert document.ai_provider == provider
    assert document.id == args["document_id"]
