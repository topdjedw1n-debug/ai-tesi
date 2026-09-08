"""Exercise the academic gates inside the leased generation pipeline."""

from contextlib import ExitStack
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from app.core.exceptions import QualityThresholdNotMetError
from app.models.document import AIGenerationJob, Document, DocumentProvenance
from app.services.academic_context import ACADEMIC_FUNCTIONS
from app.services.background_jobs import BackgroundJobService
from app.services.source_evidence import freeze_evidence
from app.services.source_verification_stage import persist_source_pack
from tests import test_source_pack_preflight_pipeline as preflight_fixtures
from tests.test_source_pack_preflight_pipeline import _preflight_settings
from tests.test_source_pack_rebuild import fake_pack, rebuild_harness, seed_document

_stub_claim_judge = preflight_fixtures._stub_claim_judge


@pytest.mark.asyncio
@pytest.mark.parametrize("outline_passes", [False, True])
async def test_outline_blocks_writer_but_whole_failure_keeps_internal_export(
    db_session, monkeypatch, outline_passes
):
    monkeypatch.setattr("app.services.background_jobs.settings", _preflight_settings())
    user, document = await seed_document(
        db_session,
        f"academic-pipeline-{outline_passes}@example.com",
        sections=["Allowed chapter"],
    )
    quote = "Compare actual study designs and limitations"
    document.outline = {
        "academic_plan": {
            "research_question": "Which nursing findings transfer?",
            "objectives": ["Compare evidence"],
        },
        "sections": [
            {
                "title": "Allowed chapter",
                "estimated_words": 500,
                "main_points": [quote],
                "academic_functions": list(ACADEMIC_FUNCTIONS),
                "evidence_keys": ["Rossi2020"],
            }
        ],
    }
    pack = fake_pack(int(document.id))
    key = pack.sources[0].citation_key
    document.outline["sections"][0]["evidence_keys"] = [key]
    source = pack.sources[0].source
    source.verification_status = "verified"
    source.canonical_metadata = {"status": "verified"}
    freeze_evidence(source, [], key)
    await persist_source_pack(db_session, int(document.id), pack)
    job = AIGenerationJob(
        user_id=user.id,
        document_id=document.id,
        job_type="full_document",
        status="running",
        lease_owner="academic-worker",
        lease_token="academic-token",
        lease_expires_at=datetime.now(UTC) + timedelta(minutes=5),
        source_pack_sha256=pack.sha256(),
    )
    db_session.add(job)
    db_session.add(
        DocumentProvenance(
            document_id=document.id,
            stage="retrieval",
            event_type="source_pack_preflight",
            payload={
                "sha256": pack.sha256(),
                "retrieval_trace": [
                    {"provider": "fixture", "query": "care", "count": 1}
                ],
            },
        )
    )
    await db_session.commit()
    await db_session.refresh(job)
    calls = []

    async def review(_prompt, *, purpose, chain_override):
        calls.append(purpose)
        passed = outline_passes and purpose == "academic_outline_review"
        return {
            "functions": {
                k: {
                    "satisfied": passed,
                    "evidence_quote": quote if passed else "",
                    "reason": "Specific substantive assessment",
                }
                for k in ACADEMIC_FUNCTIONS
            },
            "requirements_satisfied": passed,
            "source_coverage": [
                {
                    "section_index": 1,
                    "supported": passed,
                    "source_keys": [key],
                    "reason": "Specific evidence assessment",
                }
            ],
            "issues": (
                []
                if passed
                else [{"severity": "major", "reason": "Missing substantive comparison"}]
            ),
        }

    ai = MagicMock()
    ai.call_with_fallback = AsyncMock(side_effect=review)
    with ExitStack() as stack:
        mocks = rebuild_harness(stack, db_session, redis_checkpoint=None)
        stack.enter_context(
            patch(
                "app.services.background_jobs._load_source_pack",
                AsyncMock(return_value=pack),
            )
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._run_citation_verification_stage",
                AsyncMock(),
            )
        )
        stack.enter_context(
            patch("app.services.academic_review.AIService", return_value=ai)
        )
        exported = stack.enter_context(
            patch(
                "app.services.background_jobs._export_document_with_fence",
                AsyncMock(
                    return_value={"download_url": "fixture.docx", "format": "docx"}
                ),
            )
        )

        async def run():
            await BackgroundJobService.generate_full_document(
                document_id=document.id,
                user_id=user.id,
                job_id=job.id,
                lease_owner="academic-worker",
                lease_token="academic-token",
            )

        if outline_passes:
            await run()
            assert exported.await_count == 1
            assert mocks["generate_section"].await_count == 1
            assert calls == ["academic_outline_review", "academic_review"]
            current = await db_session.get(Document, document.id)
            assert current.content
            events = (
                (
                    await db_session.execute(
                        select(DocumentProvenance).where(
                            DocumentProvenance.document_id == document.id
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert (
                next(e for e in events if e.event_type == "academic_review").payload[
                    "status"
                ]
                == "failed"
            )
            assert any(e.event_type == "academic_review_artifact" for e in events)
        else:
            with pytest.raises(QualityThresholdNotMetError):
                await run()
            assert (
                exported.await_count == 0 and mocks["generate_section"].await_count == 0
            )
            assert calls == ["academic_outline_review"]
