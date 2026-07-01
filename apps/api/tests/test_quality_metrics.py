"""Unit tests for local quality-proxy metrics (quality_metrics.py)."""

from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.quality_metrics import (
    burstiness,
    citation_grounding_rate,
    connector_cliche_density,
    evidence_presence,
    outline_adherence,
    sentence_length_stats,
)


def test_burstiness_higher_for_varied_lengths():
    uniform = "one two three. one two three. one two three."
    varied = "Short. Then a considerably longer sentence with many more words here."
    assert burstiness(varied) > burstiness(uniform)


def test_sentence_length_stats_empty():
    stats = sentence_length_stats("")
    assert stats["sentences"] == 0
    assert stats["stdev"] == 0.0


def test_connector_cliche_density_detects_refrain():
    text = (
        "Tuttavia, inoltre, in conclusione serve un approccio equilibrato. "
        "Moreover, furthermore, in conclusion."
    )
    result = connector_cliche_density(text, "it")
    assert result["hits"] >= 5
    assert result["per_1000_words"] > 0


def test_connector_cliche_density_clean_text():
    result = connector_cliche_density("Students used a tutoring system daily.", "en")
    assert result["hits"] == 0


def test_evidence_presence_number():
    assert evidence_presence("AI raised scores by 30% in trials.") is True
    assert evidence_presence("AI is generally regarded as helpful.") is False


def test_outline_adherence_full_and_partial():
    promised = [
        {"title": "A", "estimated_words": 100},
        {"title": "B", "estimated_words": 100},
    ]
    full = outline_adherence(
        promised,
        [
            {"title": "A", "word_count": 90, "content": ""},
            {"title": "B", "word_count": 110, "content": ""},
        ],
    )
    assert full["adherence"] == 1.0
    assert full["fully_delivered"] is True

    partial = outline_adherence(
        promised, [{"title": "A", "word_count": 90, "content": ""}]
    )
    assert partial["adherence"] == 0.5
    assert partial["fully_delivered"] is False


def test_citation_grounding_rate_matches_gate():
    pack = SourcePack(
        document_id=1,
        topic="t",
        sources=[
            PackedSource(
                SourceDoc(title="x", authors=["Rossi"], year=2021, abstract="x"),
                "Rossi2021",
                0.9,
            )
        ],
    )
    rate = citation_grounding_rate(
        {"content": "A [Rossi2021, 2021] and B [Ghost2020, 2020]."}, pack
    )
    assert rate == 0.5
