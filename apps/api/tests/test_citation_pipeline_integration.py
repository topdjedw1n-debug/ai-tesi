"""Active citation formatter/generator library contracts; retired full executor tests are listed in evidence."""

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.config import Settings
from app.models.document import Document
from app.services.background_jobs import _map_verification_status
from app.services.citation_verifier import VerificationResult, VerificationStatus


def make_settings(**overrides) -> Settings:
    defaults = {
        "QUALITY_GATES_ENABLED": False,
        "QUALITY_MAX_REGENERATE_ATTEMPTS": 0,
        "CITATION_VERIFICATION_ENABLED": True,
        "CITATION_VERIFICATION_POLICY": "strict",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.parametrize(
    ("status", "score", "expected"),
    [
        (VerificationStatus.VERIFIED, 1.0, "verified"),
        (VerificationStatus.VERIFIED, 0.90, "verified"),
        (VerificationStatus.VERIFIED, 0.89, "mismatched"),
        (VerificationStatus.VERIFIED, None, "verified"),
        (VerificationStatus.NOT_FOUND, None, "not_found"),
        (VerificationStatus.UNRESOLVABLE, None, "failed"),
    ],
)
def test_map_verification_status_unit(status, score, expected):
    result = VerificationResult(status=status, match_score=score)
    assert _map_verification_status(result) == expected


# ----------------------------------------------------------------------
# Generator contract (SSE byte-compat)
# ----------------------------------------------------------------------

LEGACY_RESULT_KEYS = {
    "section_title",
    "section_index",
    "content",
    "citations",
    "bibliography",
    "sources_used",
    "humanized",
    # Honest writer trail (Validation-6): planned vs actual model + fallback
    # flag are unconditional — a provider outage must never swap the writer
    # invisibly.
    "writer_planned",
    "writer_actual",
    "writer_fallback_used",
}


async def _generate_with_flag(monkeypatch, enabled: bool):
    from app.services.ai_pipeline.generator import SectionGenerator
    from app.services.ai_pipeline.rag_retriever import SourceDoc

    monkeypatch.setattr(
        "app.services.ai_pipeline.generator.settings",
        make_settings(CITATION_VERIFICATION_ENABLED=enabled),
    )

    generator = SectionGenerator()
    generator.rag_retriever = MagicMock()
    generator.rag_retriever.retrieve_sources = AsyncMock(
        return_value=[
            SourceDoc(
                title="Attention Is All You Need",
                authors=["Ashish Vaswani"],
                year=2017,
                doi="10.5555/attention",
            )
        ]
    )
    generator._call_ai_with_fallback = AsyncMock(
        return_value="Attention mechanisms dominate [Vaswani, 2017]."
    )
    generator.training_collector = MagicMock()
    generator.training_collector.collect_generation_sample = AsyncMock()

    document = Document(
        id=1,
        user_id=1,
        title="T",
        topic="Transformers",
        language="en",
    )
    return await generator.generate_section(
        document=document,
        section_title="Background",
        section_index=1,
        provider="openai",
        model="gpt-4",
    )


@pytest.mark.asyncio
async def test_generator_flag_off_keys_unchanged(monkeypatch):
    """Locks the SSE byte-compat contract: no new keys when flag is off"""
    result = await _generate_with_flag(monkeypatch, enabled=False)
    assert set(result.keys()) == LEGACY_RESULT_KEYS


@pytest.mark.asyncio
async def test_generator_flag_on_adds_serializable_cited_sources(monkeypatch):
    result = await _generate_with_flag(monkeypatch, enabled=True)
    assert set(result.keys()) == LEGACY_RESULT_KEYS | {"cited_sources"}
    assert isinstance(result["cited_sources"], list)
    assert result["cited_sources"][0]["doi"] == "10.5555/attention"
    json.dumps(result)  # SSE serializability: must not raise


# ----------------------------------------------------------------------
# Frozen frontend contract (see app/schemas/provenance.py)
# ----------------------------------------------------------------------
