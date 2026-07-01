"""Unit tests for the in-loop grounding gate (grounding_gate.py)."""

from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.grounding_gate import evaluate_grounding


def _pack(*packed):
    return SourcePack(document_id=1, topic="AI in education", sources=list(packed))


def _ps(key, score, title="AI in classroom learning"):
    return PackedSource(
        SourceDoc(title=title, authors=["Rossi"], year=2021, abstract="x"),
        key,
        score,
    )


def test_grounded_content_passes():
    pack = _pack(_ps("Rossi2021", 0.9))
    result = evaluate_grounding(
        {"content": "AI improves outcomes [Rossi2021, 2021] measurably."},
        pack,
        min_grounding_rate=0.8,
        min_on_topic_score=0.35,
    )
    assert result.passed is True
    assert result.grounding_rate == 1.0
    assert result.grounded_citations == 1


def test_invented_key_fails_and_is_reported():
    pack = _pack(_ps("Rossi2021", 0.9))
    result = evaluate_grounding(
        {"content": "AI matters [Vittori, 2026] and [Ghost2020]."},
        pack,
        min_grounding_rate=0.8,
        min_on_topic_score=0.35,
    )
    assert result.passed is False
    assert result.grounding_rate == 0.0
    assert "Ghost2020" in result.offending_keys
    assert "Vittori" in result.offending_keys


def test_off_topic_pack_source_is_not_grounded():
    # Key resolves to a pack source, but its on_topic_score is below threshold.
    pack = _pack(_ps("Vittori2026", 0.1, title="AI in corporate training"))
    result = evaluate_grounding(
        {"content": "Training helps [Vittori2026, 2026]."},
        pack,
        min_grounding_rate=0.8,
        min_on_topic_score=0.35,
    )
    assert result.passed is False
    assert "Vittori2026" in result.offending_keys


def test_no_citations_fails_evidence_requirement():
    pack = _pack(_ps("Rossi2021", 0.9))
    result = evaluate_grounding(
        {"content": "A paragraph with no citations at all."},
        pack,
        min_grounding_rate=0.8,
        require_evidence=True,
        min_on_topic_score=0.35,
    )
    assert result.passed is False
    assert result.total_citations == 0


def test_partial_grounding_below_rate_fails():
    pack = _pack(_ps("Rossi2021", 0.9))
    # 1 grounded of 2 -> rate 0.5 < 0.8
    result = evaluate_grounding(
        {"content": "A [Rossi2021, 2021] and B [Ghost2020, 2020]."},
        pack,
        min_grounding_rate=0.8,
        min_on_topic_score=0.35,
    )
    assert result.grounding_rate == 0.5
    assert result.passed is False
