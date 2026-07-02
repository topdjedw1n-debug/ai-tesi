"""
Tests for the document provenance ledger.

Covers three layers:
1. Pipeline: generate_full_document writes ledger events at every stage
   (rag_retrieved, section_generated, humanized, quality_gate, citation_gate,
   exported) into document_provenance.
2. API: GET /api/v1/documents/{id}/provenance returns the chronology for the
   owner or an admin and 403s for anyone else.
3. Refunds: analyze_refund_risk uses the ledger as evidence for/against
   "low quality" complaints.

Pipeline harness mirrors test_citation_pipeline_integration.py: service mocks
over the REAL db_session (SQLite) so DocumentProvenance rows are exercised.
"""

from contextlib import ExitStack
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.core.config import Settings
from app.core.exceptions import CitationIntegrityError, QualityThresholdNotMetError
from app.core.security import create_access_token
from app.models.auth import User
from app.models.document import Document, DocumentProvenance, DocumentSource
from app.models.payment import Payment
from app.models.refund import RefundRequest
from app.services.background_jobs import BackgroundJobService
from app.services.citation_verifier import VerificationResult, VerificationStatus
from app.services.refund_service import RefundService
from main import app

# ----------------------------------------------------------------------
# Fixtures and helpers
# ----------------------------------------------------------------------

LEDGER_EVENT_TYPES = {
    "rag_retrieved",
    "section_generated",
    "humanized",
    "quality_gate",
    "citation_gate",
    "exported",
}

SOURCE_A = {
    "title": "Attention Is All You Need",
    "authors": ["Ashish Vaswani"],
    "year": 2017,
    "abstract": None,
    "paper_id": None,
    "venue": "NeurIPS",
    "citation_count": 100,
    "url": None,
    "doi": "10.5555/attention",
}
SOURCE_B = {
    "title": "BERT: Pre-training of Deep Bidirectional Transformers",
    "authors": ["Jacob Devlin"],
    "year": 2019,
    "abstract": None,
    "paper_id": None,
    "venue": "NAACL",
    "citation_count": 50,
    "url": None,
    "doi": None,
}


def make_settings(**overrides) -> Settings:
    defaults = {
        "QUALITY_GATES_ENABLED": False,
        "QUALITY_MAX_REGENERATE_ATTEMPTS": 0,
        "CITATION_VERIFICATION_ENABLED": True,
        "CITATION_VERIFICATION_POLICY": "mark_only",
        "PROVENANCE_LEDGER_ENABLED": True,
    }
    defaults.update(overrides)
    return Settings(**defaults)


def vres(status, title="T", score=1.0) -> VerificationResult:
    return VerificationResult(
        status=status,
        title=title,
        match_score=score,
        provider="crossref" if status == VerificationStatus.VERIFIED else None,
    )


def verifier_by_title(status_by_title):
    def _side_effect(inputs):
        return [
            status_by_title.get(
                s.title, vres(VerificationStatus.VERIFIED, title=s.title)
            )
            for s in inputs
        ]

    return _side_effect


async def seed_document(db_session, section_titles=("Introduction", "Methods")):
    user = User(email="ledger-test@example.com", full_name="Ledger Tester")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    document = Document(
        user_id=user.id,
        title="Provenance Test Thesis",
        topic="AI in Education",
        status="draft",
        language="en",
        ai_provider="openai",
        ai_model="gpt-4",
        outline={"sections": [{"title": t} for t in section_titles]},
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    return user, document


def section_result(index, cited_sources):
    return {
        "section_title": f"Section {index}",
        "section_index": index,
        "content": f"Generated content for section {index}",
        "citations": [],
        "bibliography": ["ref"],
        "sources_used": len(cited_sources),
        "humanized": False,
        "cited_sources": cited_sources,
    }


def ai_check_filling_trace(
    content, threshold, humanizer, provider, model, language, score_trace=None, **_
):
    """Mock _check_ai_detection_quality that also fills the provenance trace"""
    if score_trace is not None:
        score_trace["initial_ai_score"] = 60.0
        score_trace["final_ai_score"] = 20.0
        score_trace["multi_pass"] = True
    return (20.0, content, "mock", "passed", None)


def pipeline_harness(
    stack: ExitStack,
    db_session,
    mock_redis,
    *,
    generate_side_effect,
    verifier_side_effect=None,
    grammar_side_effect=None,
):
    """Standard patch block over the real db_session; returns mocks dict"""
    mocks = {}

    gen_class = stack.enter_context(
        patch("app.services.background_jobs.SectionGenerator")
    )
    generator = MagicMock()
    generator.generate_section = AsyncMock(side_effect=generate_side_effect)
    gen_class.return_value = generator
    mocks["generate_section"] = generator.generate_section

    humanizer_class = stack.enter_context(
        patch("app.services.background_jobs.Humanizer")
    )
    humanizer = MagicMock()
    humanizer.humanize = AsyncMock(
        side_effect=lambda *a, **k: k.get("text", "Humanized")
    )
    humanizer_class.return_value = humanizer

    quality_class = stack.enter_context(
        patch("app.services.background_jobs.QualityValidator")
    )
    quality_validator = MagicMock()
    quality_validator.validate_section = AsyncMock(
        return_value={"overall_score": 85.0, "issues": []}
    )
    quality_class.return_value = quality_validator

    stack.enter_context(
        patch(
            "app.services.background_jobs._check_grammar_quality",
            AsyncMock(
                side_effect=grammar_side_effect if grammar_side_effect else None,
                return_value=(95.0, 0, "passed", None),
            ),
        )
    )
    stack.enter_context(
        patch(
            "app.services.background_jobs._check_plagiarism_quality",
            AsyncMock(return_value=(5.0, 95.0, "passed", None)),
        )
    )
    stack.enter_context(
        patch(
            "app.services.background_jobs._check_ai_detection_quality",
            AsyncMock(side_effect=ai_check_filling_trace),
        )
    )

    manager = stack.enter_context(patch("app.services.background_jobs.manager"))
    manager.send_progress = AsyncMock()
    mocks["manager"] = manager

    doc_service_class = stack.enter_context(
        patch("app.services.background_jobs.DocumentService")
    )
    doc_service = MagicMock()
    doc_service.export_document = AsyncMock(
        return_value={
            "download_url": "https://example.com/doc.docx",
            "format": "docx",
            "file_size": 12345,
        }
    )
    doc_service_class.return_value = doc_service
    mocks["export_document"] = doc_service.export_document

    stack.enter_context(
        patch(
            "app.services.background_jobs.get_redis",
            AsyncMock(return_value=mock_redis),
        )
    )

    session_class = stack.enter_context(
        patch("app.services.background_jobs.database.AsyncSessionLocal")
    )
    mock_session = MagicMock()
    mock_session.__aenter__ = AsyncMock(return_value=db_session)
    mock_session.__aexit__ = AsyncMock(return_value=None)
    session_class.return_value = mock_session

    verifier_class = stack.enter_context(
        patch("app.services.background_jobs.CitationVerifier")
    )
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(
        side_effect=(
            verifier_side_effect if verifier_side_effect else verifier_by_title({})
        )
    )
    verifier_class.return_value = verifier

    stack.enter_context(patch("app.services.notification_service.notification_service"))

    return mocks


@pytest.fixture
def mock_redis():
    redis = MagicMock()
    redis.get = AsyncMock(return_value=None)
    redis.set = AsyncMock()
    redis.delete = AsyncMock()
    return redis


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac


async def ordered_events(db_session, document_id) -> list[DocumentProvenance]:
    result = await db_session.execute(
        select(DocumentProvenance)
        .where(DocumentProvenance.document_id == document_id)
        .order_by(DocumentProvenance.id.asc())
    )
    return list(result.scalars().all())


# ----------------------------------------------------------------------
# 1. Pipeline writes events at every stage
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_pipeline_writes_events_for_all_stages(
    db_session, mock_redis, monkeypatch
):
    monkeypatch.setattr("app.services.background_jobs.settings", make_settings())
    user, document = await seed_document(db_session)
    document_id = document.id

    with ExitStack() as stack:
        pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[
                section_result(1, [SOURCE_A]),
                section_result(2, [SOURCE_B]),
            ],
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )

    events = await ordered_events(db_session, document_id)
    types = [e.event_type for e in events]

    # All six required ledger event types present
    assert LEDGER_EVENT_TYPES <= set(types)

    # One section-stage event per section
    assert types.count("rag_retrieved") == 2
    assert types.count("section_generated") == 2
    assert types.count("humanized") == 2
    assert types.count("quality_gate") == 2

    # Chronology: sections -> verification -> export, export is terminal
    assert types.index("rag_retrieved") < types.index("verification_summary")
    assert types.index("citation_gate") < types.index("exported")
    assert types[-1] == "exported"

    by_type: dict[str, list[DocumentProvenance]] = {}
    for event in events:
        by_type.setdefault(event.event_type, []).append(event)

    rag = by_type["rag_retrieved"][0]
    assert rag.stage == "retrieval"
    assert rag.payload["section_index"] == 1
    assert rag.payload["sources"] == [
        {
            "title": SOURCE_A["title"],
            "doi": SOURCE_A["doi"],
            "year": SOURCE_A["year"],
            "verification_status": "unverified",
        }
    ]

    gen = by_type["section_generated"][0]
    assert gen.stage == "generation"
    assert gen.payload["provider"] == "openai"
    assert gen.payload["model"] == "gpt-4"
    assert gen.payload["word_count"] > 0
    assert gen.payload["attempts"] == 1

    hum = by_type["humanized"][0]
    assert hum.stage == "generation"
    assert hum.payload["ai_score_before"] == 60.0
    assert hum.payload["ai_score_after"] == 20.0
    assert hum.payload["multi_pass"] is True

    gate = by_type["quality_gate"][0]
    assert gate.stage == "quality"
    assert gate.payload["passed"] is True
    assert gate.payload["status"] == "passed"
    assert gate.payload["grammar_score"] == 95.0
    assert gate.payload["plagiarism_score"] == 5.0
    assert gate.payload["ai_detection_score"] == 20.0
    assert gate.payload["quality_score"] == 85.0
    checks = gate.payload["checks"]
    assert checks["grammar"] == {"status": "passed", "score": 95.0, "reason": None}
    assert checks["plagiarism"] == {"status": "passed", "score": 5.0, "reason": None}
    assert checks["ai_detection"] == {
        "status": "passed",
        "score": 20.0,
        "reason": None,
        "provider": "mock",
    }

    summary = by_type["verification_summary"][0]
    assert summary.payload["providers"] == ["crossref"]
    summary_sources = summary.payload["sources"]
    assert {s["status"] for s in summary_sources} == {"verified"}
    assert summary_sources[0]["title"] == SOURCE_A["title"]
    assert summary_sources[0]["authors"] == SOURCE_A["authors"]
    assert summary_sources[0]["year"] == SOURCE_A["year"]
    assert summary_sources[0]["doi"] == SOURCE_A["doi"]

    citation = by_type["citation_gate"][-1]
    assert citation.stage == "verification"
    assert citation.payload["passed"] is True
    assert citation.payload["counts"] == {"verified": 2}

    exported = by_type["exported"][0]
    assert exported.stage == "export"
    assert exported.payload["formats"] == ["docx"]
    assert exported.payload["paths"]["docx"] == "https://example.com/doc.docx"
    assert exported.payload["file_size"] == 12345


@pytest.mark.asyncio
async def test_ledger_flag_off_writes_no_ledger_events(
    db_session, mock_redis, monkeypatch
):
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        make_settings(PROVENANCE_LEDGER_ENABLED=False),
    )
    user, document = await seed_document(db_session)
    document_id = document.id

    with ExitStack() as stack:
        pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[
                section_result(1, [SOURCE_A]),
                section_result(2, [SOURCE_B]),
            ],
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )

    types = {e.event_type for e in await ordered_events(db_session, document_id)}
    assert not (LEDGER_EVENT_TYPES & types)
    # Legacy verification events are gated by CITATION_VERIFICATION_ENABLED only
    assert "verification_summary" in types


@pytest.mark.asyncio
async def test_quality_gate_failure_writes_failed_event(
    db_session, mock_redis, monkeypatch
):
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        make_settings(QUALITY_GATES_ENABLED=True, QUALITY_MAX_REGENERATE_ATTEMPTS=0),
    )
    user, document = await seed_document(db_session, section_titles=("Only",))
    document_id = document.id

    with ExitStack() as stack:
        pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[section_result(1, [SOURCE_A])],
            grammar_side_effect=[(40.0, 25, "failed", "Grammar: 25 errors (max: 5)")],
        )
        with pytest.raises(QualityThresholdNotMetError):
            await BackgroundJobService.generate_full_document(
                document_id=document_id, user_id=user.id
            )

    events = await ordered_events(db_session, document_id)
    types = [e.event_type for e in events]
    # Section was never accepted -> no accepted-section events
    assert "section_generated" not in types
    assert "exported" not in types

    failed_gate = next(e for e in events if e.event_type == "quality_gate")
    assert failed_gate.stage == "quality"
    assert failed_gate.payload["passed"] is False
    assert failed_gate.payload["status"] == "failed"
    assert failed_gate.payload["section_index"] == 1
    assert "Grammar" in failed_gate.payload["detail"]


@pytest.mark.asyncio
async def test_unchecked_gate_is_nonblocking_but_recorded(
    db_session, mock_redis, monkeypatch
):
    """Stage B core case: provider down (e.g. GPTZero off) must NOT fail the
    job or trigger regeneration, but the quality_gate event must record
    status='unchecked' with passed=False — never a silent pass."""
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        make_settings(QUALITY_GATES_ENABLED=True, QUALITY_MAX_REGENERATE_ATTEMPTS=2),
    )
    user, document = await seed_document(db_session, section_titles=("Only",))
    document_id = document.id

    def ai_unchecked(content, *a, **k):
        return (None, content, "none", "unchecked", "AI detection is disabled")

    with ExitStack() as stack:
        mocks = pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[section_result(1, [SOURCE_A])],
            # grammar also unchecked; plagiarism passes (harness default)
            grammar_side_effect=[(None, 0, "unchecked", "LanguageTool is disabled")],
        )
        stack.enter_context(
            patch(
                "app.services.background_jobs._check_ai_detection_quality",
                AsyncMock(side_effect=ai_unchecked),
            )
        )
        await BackgroundJobService.generate_full_document(
            document_id=document_id, user_id=user.id
        )
        # Non-blocking: exactly one attempt, no regeneration
        assert mocks["generate_section"].call_count == 1

    events = await ordered_events(db_session, document_id)
    gate = next(e for e in events if e.event_type == "quality_gate")
    assert gate.payload["status"] == "unchecked"
    assert gate.payload["passed"] is False  # no reader may see this as passed
    checks = gate.payload["checks"]
    assert checks["grammar"]["status"] == "unchecked"
    assert checks["grammar"]["reason"] == "LanguageTool is disabled"
    assert checks["ai_detection"]["status"] == "unchecked"
    assert checks["ai_detection"]["provider"] == "none"
    assert checks["plagiarism"]["status"] == "passed"
    # Section was accepted and exported despite unchecked checks
    types = [e.event_type for e in events]
    assert "section_generated" in types
    assert "exported" in types


@pytest.mark.asyncio
async def test_strict_citation_gate_failure_writes_failed_event(
    db_session, mock_redis, monkeypatch
):
    monkeypatch.setattr(
        "app.services.background_jobs.settings",
        make_settings(CITATION_VERIFICATION_POLICY="strict"),
    )
    user, document = await seed_document(db_session)
    document_id = document.id

    with ExitStack() as stack:
        pipeline_harness(
            stack,
            db_session,
            mock_redis,
            generate_side_effect=[
                section_result(1, [SOURCE_A]),
                section_result(2, [SOURCE_B]),
            ],
            verifier_side_effect=verifier_by_title(
                {
                    SOURCE_B["title"]: vres(
                        VerificationStatus.NOT_FOUND, title=SOURCE_B["title"]
                    )
                }
            ),
        )
        with pytest.raises(CitationIntegrityError):
            await BackgroundJobService.generate_full_document(
                document_id=document_id, user_id=user.id
            )

    events = await ordered_events(db_session, document_id)
    citation = next(e for e in events if e.event_type == "citation_gate")
    assert citation.payload["passed"] is False
    assert citation.payload["policy"] == "strict"
    assert citation.payload["not_found_count"] == 1
    assert SOURCE_B["title"] in citation.payload["not_found_titles"]
    assert "exported" not in {e.event_type for e in events}


# ----------------------------------------------------------------------
# 2. GET /api/v1/documents/{id}/provenance
# ----------------------------------------------------------------------


async def seed_endpoint_case(db_session):
    owner = User(email="prov-owner@test.com", full_name="Owner", is_active=True)
    other = User(email="prov-other@test.com", full_name="Other", is_active=True)
    admin = User(
        email="prov-admin@test.com", full_name="Admin", is_active=True, is_admin=True
    )
    db_session.add_all([owner, other, admin])
    await db_session.commit()
    for user in (owner, other, admin):
        await db_session.refresh(user)

    document = Document(
        user_id=owner.id, title="Provenance Doc", topic="AI in Education"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    db_session.add_all(
        [
            DocumentProvenance(
                document_id=document.id,
                stage="retrieval",
                event_type="rag_retrieved",
                payload={"section_index": 1, "sources_used": 3},
            ),
            DocumentProvenance(
                document_id=document.id,
                stage="quality",
                event_type="quality_gate",
                payload={"section_index": 1, "passed": True},
            ),
            DocumentProvenance(
                document_id=document.id,
                stage="export",
                event_type="exported",
                payload={"formats": ["docx"]},
            ),
        ]
    )
    await db_session.commit()
    return owner, other, admin, document


def auth_headers_for(user: User) -> dict[str, str]:
    return {"Authorization": f"Bearer {create_access_token(user_id=user.id)}"}


@pytest.mark.asyncio
async def test_provenance_endpoint_owner_gets_chronology(client, db_session):
    owner, _, _, document = await seed_endpoint_case(db_session)

    response = await client.get(
        f"/api/v1/documents/{document.id}/provenance",
        headers=auth_headers_for(owner),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["document_id"] == document.id
    assert body["total"] == 3
    assert [e["event_type"] for e in body["events"]] == [
        "rag_retrieved",
        "quality_gate",
        "exported",
    ]
    assert [e["stage"] for e in body["events"]] == ["retrieval", "quality", "export"]
    assert body["events"][0]["payload"] == {"section_index": 1, "sources_used": 3}
    assert all(e["created_at"] is not None for e in body["events"])


@pytest.mark.asyncio
async def test_provenance_endpoint_foreign_user_gets_403(client, db_session):
    _, other, _, document = await seed_endpoint_case(db_session)

    response = await client.get(
        f"/api/v1/documents/{document.id}/provenance",
        headers=auth_headers_for(other),
    )

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_provenance_endpoint_admin_gets_200(client, db_session):
    _, _, admin, document = await seed_endpoint_case(db_session)

    response = await client.get(
        f"/api/v1/documents/{document.id}/provenance",
        headers=auth_headers_for(admin),
    )

    assert response.status_code == 200
    assert response.json()["total"] == 3


@pytest.mark.asyncio
async def test_provenance_endpoint_missing_document_404(client, db_session):
    owner, _, _, _ = await seed_endpoint_case(db_session)

    response = await client.get(
        "/api/v1/documents/999999/provenance",
        headers=auth_headers_for(owner),
    )

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_provenance_endpoint_requires_auth(client, db_session):
    _, _, _, document = await seed_endpoint_case(db_session)

    response = await client.get(f"/api/v1/documents/{document.id}/provenance")

    assert response.status_code == 401


# ----------------------------------------------------------------------
# 3. Refund risk uses provenance evidence
# ----------------------------------------------------------------------


async def seed_refund_case(db_session, *, category="quality", amount=Decimal("50.00")):
    user = User(email="refund-prov@test.com", full_name="Refund User", is_active=True)
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    document = Document(user_id=user.id, title="Paid Doc", topic="AI in Education")
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    payment = Payment(
        user_id=user.id,
        document_id=document.id,
        amount=amount,
        currency="EUR",
        status="completed",
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(payment)

    refund = RefundRequest(
        user_id=user.id,
        payment_id=payment.id,
        reason="The document quality is unacceptable",
        reason_category=category,
        status="pending",
    )
    db_session.add(refund)
    await db_session.commit()
    await db_session.refresh(refund)
    return user, document, payment, refund


def gate_event(document_id, event_type, payload):
    return DocumentProvenance(
        document_id=document_id,
        stage="quality" if event_type == "quality_gate" else "verification",
        event_type=event_type,
        payload=payload,
    )


@pytest.mark.asyncio
async def test_refund_risk_increases_for_fully_verified_document(db_session):
    """100% verified sources + passed gates contradict a 'low quality' claim"""
    user, document, payment, refund = await seed_refund_case(db_session)

    db_session.add_all(
        [
            DocumentSource(
                document_id=document.id,
                title="Verified One",
                doi="10.1/one",
                verification_status="verified",
            ),
            DocumentSource(
                document_id=document.id,
                title="Verified Two",
                verification_status="verified",
            ),
            gate_event(
                document.id,
                "quality_gate",
                {"section_index": 1, "passed": True, "status": "passed"},
            ),
            gate_event(
                document.id,
                "quality_gate",
                {"section_index": 2, "passed": True, "status": "passed"},
            ),
            gate_event(
                document.id,
                "citation_gate",
                {"passed": True, "status": "passed", "counts": {"verified": 2}},
            ),
        ]
    )
    await db_session.commit()

    result = await RefundService(db_session).analyze_refund_risk(refund.id)

    assert result["risk_score"] == pytest.approx(0.3)
    assert result["recommendation"] == "review"
    provenance = result["factors"]["provenance"]
    assert provenance["all_sources_verified"] is True
    assert provenance["quality_gates_passed"] is True
    assert provenance["citation_gate_passed"] is True

    refreshed = (
        await db_session.execute(
            select(RefundRequest).where(RefundRequest.id == refund.id)
        )
    ).scalar_one()
    assert refreshed.risk_score == pytest.approx(0.3)


@pytest.mark.asyncio
async def test_refund_risk_decreases_when_ledger_supports_complaint(db_session):
    """not_found sources / failed gates support the claim -> lower risk"""
    user, document, payment, refund = await seed_refund_case(
        db_session, amount=Decimal("150.00")  # base +0.2 so the -0.2 is observable
    )

    db_session.add_all(
        [
            DocumentSource(
                document_id=document.id,
                title="Phantom Source",
                verification_status="not_found",
            ),
            gate_event(
                document.id,
                "quality_gate",
                {"section_index": 1, "passed": False, "detail": "Grammar"},
            ),
        ]
    )
    await db_session.commit()

    result = await RefundService(db_session).analyze_refund_risk(refund.id)

    assert result["risk_score"] == pytest.approx(0.0)  # 0.2 base - 0.2 evidence
    assert result["recommendation"] == "approve"
    provenance = result["factors"]["provenance"]
    assert provenance["not_found_sources"] == 1
    assert provenance["quality_gate_failures"] == 1
    assert provenance["all_sources_verified"] is False


@pytest.mark.asyncio
async def test_refund_risk_treats_legacy_scoreless_gates_as_unchecked(db_session):
    """Legacy fail-open events (passed=True, no scores) are not quality proof:
    they derive 'unchecked', so risk must NOT increase as if gates passed."""
    user, document, payment, refund = await seed_refund_case(db_session)

    db_session.add_all(
        [
            DocumentSource(
                document_id=document.id,
                title="Verified One",
                verification_status="verified",
            ),
            # Legacy shape: no status key, no check scores
            gate_event(
                document.id, "quality_gate", {"section_index": 1, "passed": True}
            ),
        ]
    )
    await db_session.commit()

    result = await RefundService(db_session).analyze_refund_risk(refund.id)

    provenance = result["factors"]["provenance"]
    assert provenance["quality_gates_passed"] is False  # unchecked, not proven
    assert provenance["quality_gate_failures"] == 0  # but not a failure either


@pytest.mark.asyncio
async def test_refund_risk_ignores_provenance_for_non_quality_category(db_session):
    user, document, payment, refund = await seed_refund_case(
        db_session, category="technical_issue"
    )
    db_session.add(
        gate_event(document.id, "quality_gate", {"section_index": 1, "passed": True})
    )
    await db_session.commit()

    result = await RefundService(db_session).analyze_refund_risk(refund.id)

    assert result["risk_score"] == pytest.approx(0.1)  # technical_issue base only
    assert result["factors"]["provenance"] is None


@pytest.mark.asyncio
async def test_refund_risk_unchanged_without_provenance(db_session):
    """Quality complaint on a legacy document (no ledger) -> no adjustment"""
    user, document, payment, refund = await seed_refund_case(db_session)

    result = await RefundService(db_session).analyze_refund_risk(refund.id)

    assert result["risk_score"] == pytest.approx(0.0)
    provenance = result["factors"]["provenance"]
    assert provenance["has_provenance"] is False
