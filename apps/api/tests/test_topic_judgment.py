"""The document judgment in the uncertain band of the topic gate (17.09.2026)."""

import asyncio
import re
from types import SimpleNamespace

import pytest

from app.services import topic_judgment
from app.services.ai_pipeline.rag_retriever import SourceDoc
from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
from app.services.full_text_sources import document_windows, full_text_usable
from app.services.source_evidence import evidence_text, freeze_evidence
from app.services.topic_judgment import (
    JUDGE_BAND,
    MAX_JUDGMENTS,
    candidates,
    judge_documents,
    parse_verdict,
    pick_windows,
)

TOPIC = "L'uso dei social media e il benessere psicologico degli adolescenti"
NODES = [
    {
        "scope_id": "scope-2",
        "title": "Uso dei social media",
        "terms_local": ["social media", "adolescenti"],
        "terms_en": ["social media use", "adolescents"],
        "required": True,
    },
    {
        "scope_id": "scope-3",
        "title": "Fear of missing out",
        "terms_local": ["fomo"],
        "terms_en": ["fear of missing out"],
        "required": True,
    },
]
PATTERN = re.compile(r"\b(?:social|media\b|adoles|beness|fomo\b)")


def packed(key, title, pages, abstract="Sintesi del lavoro."):
    source = SourceDoc(
        title=title,
        authors=["Rossi, Maria"],
        year=2024,
        abstract=abstract,
        doi=f"10.1/{key}",
        provider="openalex",
        canonical_metadata={},
    )
    windows = document_windows(key, f"https://r.test/{key}.pdf", pages)
    freeze_evidence(source, windows, key, query=TOPIC)
    source.canonical_metadata["evidence_level"] = "pdf"
    return PackedSource(source, key, 1.0), windows


def pages_with_share(share, n=10):
    on = "Adolescenti e social media: benessere psicologico e uso quotidiano. " * 12
    off = "Coltivazione del frumento in pianura padana e resa per ettaro annuale. " * 12
    return [on if i < round(share * n) else off for i in range(n)]


def test_pick_windows_are_three_distinct_reproducible_excerpts():
    _, windows = packed("K1", "t", pages_with_share(0.6, 12))
    chosen = pick_windows(windows, PATTERN)
    assert 1 <= len(chosen) <= 3 and len({id(w) for w in chosen}) == len(chosen)
    assert chosen == pick_windows(windows, PATTERN)
    assert chosen[0] is next(w for w in windows if PATTERN.search(w.text.casefold()))
    assert pick_windows([], PATTERN) == []


def test_parse_verdict_reads_json_and_survives_cut_answers():
    assert (
        parse_verdict('{"verdict": "reject", "scope_ids": [], "reason": "x"}')[
            "verdict"
        ]
        == "reject"
    )
    cut = '{"verdict": "allow", "population_match": false, "scope_ids": ["scope-2", 3], "reason": "the'
    parsed = parse_verdict(cut)
    assert parsed["verdict"] == "allow" and parsed["scope_ids"] == []
    assert parse_verdict("no json here") is None
    assert parse_verdict('{"verdict": "maybe"}') is None


def test_candidates_are_the_fetched_documents_in_the_band_lowest_first():
    rows = []
    passages = []
    for key, share in (("KLOW", 0.3), ("KMID", 0.7), ("KHIGH", 0.95), ("KEDGE", 0.5)):
        p, w = packed(key, key, pages_with_share(share))
        rows.append(p)
        passages += w
    abstract_only = PackedSource(
        SourceDoc(
            title="abs",
            authors=[],
            year=2020,
            canonical_metadata={"evidence_level": "abstract"},
        ),
        "KABS",
        1.0,
    )
    rows.append(abstract_only)
    pack = SourcePack(1, TOPIC, sources=rows, passages=passages)
    chosen = candidates(pack, PATTERN)
    keys = [p.citation_key for _, p in chosen]
    assert keys == ["KEDGE", "KMID"]  # 0.5 in, 0.9+ and <0.5 out, lowest share first
    assert all(JUDGE_BAND[0] <= s < JUDGE_BAND[1] for s, _ in chosen)
    many = [
        packed(f"KM{i}", f"m{i}", pages_with_share(0.6))[0]
        for i in range(MAX_JUDGMENTS + 3)
    ]
    big = SourcePack(
        1,
        TOPIC,
        sources=many,
        passages=[
            w
            for i in range(MAX_JUDGMENTS + 3)
            for w in packed(f"KM{i}", f"m{i}", pages_with_share(0.6))[1]
        ],
    )
    assert len(candidates(big, PATTERN)) == MAX_JUDGMENTS


@pytest.mark.asyncio
async def test_judge_rejects_only_on_a_clear_reject_and_keeps_the_abstract():
    calls = []
    answers = {
        "KREJ": '{"verdict": "reject", "population_match": false, "scope_ids": [], "reason": "healthcare workers, another question"}',
        "KOK": '{"verdict": "allow", "population_match": false, "scope_ids": ["scope-2"], "reason": "same phenomenon"}',
        "KUNC": '{"verdict": "uncertain", "scope_ids": [], "reason": "not enough"}',
        "KBAD": "I cannot tell.",
    }

    async def fake_call(ctx, prompt, *, budget, purpose, model, counted):
        assert counted is False
        key = next(k for k in answers if f"title-{k}" in prompt)
        calls.append((key, purpose, model, budget))
        if key == "KERR":
            raise RuntimeError("provider down")
        return answers[key], False

    rows, passages = [], []
    for key in ("KREJ", "KOK", "KUNC", "KBAD"):
        p, w = packed(
            key, f"title-{key}", pages_with_share(0.6), abstract=f"Abstract {key}."
        )
        rows.append(p)
        passages += w
    pack = SourcePack(1, TOPIC, sources=rows, passages=passages)
    ctx = SimpleNamespace(
        inputs={"brief": {"additional_requirements": "Livello: magistrale."}}
    )
    results = await judge_documents(ctx, pack, NODES, PATTERN, call=fake_call)
    by_key = {r["key"]: r for r in results}
    assert [c[1:] for c in calls] == [
        ("S2_judge", topic_judgment.JUDGE_MODEL, topic_judgment.JUDGE_MAX_TOKENS)
    ] * 4
    assert (
        by_key["KREJ"]["verdict"] == "reject"
        and by_key["KBAD"]["verdict"] == "unreadable"
    )
    assert (
        by_key["KOK"]["scope_ids"] == ["scope-2"]
        and by_key["KUNC"]["verdict"] == "uncertain"
    )
    rejected = pack.by_key("KREJ").source
    # The rejected document hands no pages: excerpt from the abstract only, level back to abstract.
    assert (
        evidence_text(rejected) == "Abstract KREJ."
        and rejected.canonical_metadata["evidence_level"] == "abstract"
    )
    assert rejected.canonical_metadata["topic_judgment"]["verdict"] == "reject"
    assert not full_text_usable(pack, "KREJ", NODES, PATTERN)
    # allow, uncertain and unreadable change nothing.
    for key in ("KOK", "KUNC", "KBAD"):
        source = pack.by_key(key).source
        assert source.canonical_metadata["evidence_level"] == "pdf"
        assert "[page " in evidence_text(source)
        assert full_text_usable(pack, key, NODES, PATTERN)


@pytest.mark.asyncio
async def test_a_provider_failure_never_blocks_the_stage():
    async def failing(ctx, prompt, *, budget, purpose, model, counted):
        raise RuntimeError("provider down")

    p, w = packed("KERR", "title-KERR", pages_with_share(0.6))
    pack = SourcePack(1, TOPIC, sources=[p], passages=w)
    ctx = SimpleNamespace(inputs={"brief": {}})
    results = await judge_documents(ctx, pack, NODES, PATTERN, call=failing)
    assert (
        results[0]["verdict"] == "unreadable" and results[0]["error"] == "RuntimeError"
    )
    assert full_text_usable(pack, "KERR", NODES, PATTERN)


def test_judge_band_and_cap_are_the_calibrated_values():
    assert JUDGE_BAND == (0.5, 0.9) and MAX_JUDGMENTS == 12
    assert asyncio.iscoroutinefunction(judge_documents)


def test_every_warning_code_the_services_emit_is_registered():
    """Job 30 (17.09) failed on an unregistered code: the real context looks
    the code up in the closed vocabulary before it can warn."""
    import re
    from pathlib import Path

    from app.services.executor_v2.warnings import WARNING_CODES

    root = Path(__file__).resolve().parents[1] / "app" / "services"
    used = set()
    for path in root.rglob("*.py"):
        used.update(re.findall(r'\.warn\(\s*"([a-z_]+)"', path.read_text()))
    assert used and used <= set(WARNING_CODES), sorted(used - set(WARNING_CODES))
