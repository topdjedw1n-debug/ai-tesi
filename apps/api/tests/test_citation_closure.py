from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy import select

from app.core.config import Settings
from app.core.exceptions import CitationIntegrityError
from app.models.auth import User
from app.models.document import (
    Document,
    DocumentProvenance,
    DocumentSection,
    DocumentSource,
)
from app.services.citation_verifier import VerificationResult, VerificationStatus
from app.services.source_verification_stage import run_citation_verification_stage


async def _seed(db_session, *, used_keys: list[str], source_keys: list[str]):
    user = User(email=f"closure-{len(used_keys)}@example.com", full_name="Closure")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    document = Document(
        user_id=int(user.id),
        title="Closure Test",
        topic="Academic integrity",
        status="sections_generated",
        language="en",
        ai_provider="openai",
        ai_model="gpt-4",
        citation_style="apa",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    db_session.add(
        DocumentSection(
            document_id=int(document.id),
            section_index=1,
            title="Section",
            content="Claim (Rossi, 2021).",
            status="completed",
            pack_keys_used=used_keys,
        )
    )
    for index, key in enumerate(source_keys):
        db_session.add(
            DocumentSource(
                document_id=int(document.id),
                title=f"Paper {key}",
                authors=["Mario Rossi"],
                year=2021 + index,
                citation_key=key,
                on_topic_score=1.0,
                is_in_upfront_pack=True,
                verification_status="unverified",
            )
        )
    await db_session.commit()
    return user, document


def _settings() -> Settings:
    return Settings(
        CITATION_VERIFICATION_ENABLED=True,
        CITATION_VERIFICATION_POLICY="strict",
        PROVENANCE_LEDGER_ENABLED=True,
    )


def _verifier(*statuses: VerificationStatus):
    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(
        return_value=[
            VerificationResult(
                status=status,
                title="Canonical",
                authors=["Mario Rossi"],
                year=2021 + index,
                match_score=1.0 if status == VerificationStatus.VERIFIED else None,
                provider=(
                    "crossref" if status == VerificationStatus.VERIFIED else None
                ),
                reason=(
                    "provider_errors"
                    if status == VerificationStatus.UNRESOLVABLE
                    else None
                ),
            )
            for index, status in enumerate(statuses)
        ]
    )
    return verifier


@pytest.mark.asyncio
async def test_missing_used_key_fails_strict_closure(db_session):
    user, document = await _seed(
        db_session,
        used_keys=["Rossi2021", "Bianchi2022"],
        source_keys=["Rossi2021"],
    )
    verifier = _verifier(VerificationStatus.VERIFIED)

    with pytest.raises(CitationIntegrityError, match="closure failed"):
        await run_citation_verification_stage(
            db_session,
            int(document.id),
            int(user.id),
            config=_settings(),
            verifier_factory=lambda: verifier,
            send_progress=AsyncMock(),
        )

    events = (
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.document_id == int(document.id),
                    DocumentProvenance.event_type == "citation_closure",
                )
            )
        )
        .scalars()
        .all()
    )
    assert events[-1].payload["passed"] is False
    assert events[-1].payload["missing_keys"] == ["Bianchi2022"]


@pytest.mark.asyncio
async def test_all_used_keys_missing_still_records_failed_closure(db_session):
    user, document = await _seed(
        db_session,
        used_keys=["Rossi2021"],
        source_keys=[],
    )

    with pytest.raises(CitationIntegrityError, match="no cited sources"):
        await run_citation_verification_stage(
            db_session,
            int(document.id),
            int(user.id),
            config=_settings(),
            verifier_factory=lambda: _verifier(),
            send_progress=AsyncMock(),
        )

    event = (
        await db_session.execute(
            select(DocumentProvenance).where(
                DocumentProvenance.document_id == int(document.id),
                DocumentProvenance.event_type == "citation_closure",
            )
        )
    ).scalar_one()
    assert event.payload["passed"] is False
    assert event.payload["missing_keys"] == ["Rossi2021"]


@pytest.mark.asyncio
async def test_all_used_keys_verified_pass_closure(db_session):
    user, document = await _seed(
        db_session,
        used_keys=["Rossi2021", "Bianchi2022"],
        source_keys=["Rossi2021", "Bianchi2022"],
    )
    verifier = _verifier(
        VerificationStatus.VERIFIED,
        VerificationStatus.VERIFIED,
    )

    await run_citation_verification_stage(
        db_session,
        int(document.id),
        int(user.id),
        config=_settings(),
        verifier_factory=lambda: verifier,
        send_progress=AsyncMock(),
    )

    event = (
        await db_session.execute(
            select(DocumentProvenance).where(
                DocumentProvenance.document_id == int(document.id),
                DocumentProvenance.event_type == "citation_closure",
            )
        )
    ).scalar_one()
    assert event.payload["passed"] is True
    assert event.payload["used_total"] == 2
    assert event.payload["verified_total"] == 2


@pytest.mark.asyncio
async def test_unchecked_used_key_fails_strict_closure(db_session):
    user, document = await _seed(
        db_session,
        used_keys=["Rossi2021"],
        source_keys=["Rossi2021"],
    )
    verifier = _verifier(VerificationStatus.UNRESOLVABLE)

    with pytest.raises(CitationIntegrityError, match="could not be checked"):
        await run_citation_verification_stage(
            db_session,
            int(document.id),
            int(user.id),
            config=_settings(),
            verifier_factory=lambda: verifier,
            send_progress=AsyncMock(),
        )
