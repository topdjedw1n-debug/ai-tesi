"""Topic-anchored S2 queries on the recorded scope trees of 15.09.2026.

The trees are the real S1 output of the three cabinet works (economics A,
informatics C, law B); A's pack titles are the real S2 result that came back
off-topic. No model or catalogue is called.
"""

import json
from pathlib import Path

import pytest

from app.services.search_queries import (
    anchors,
    is_structural,
    on_topic,
    plan,
    topic_core,
)

FIXTURES = Path(__file__).parent / "fixtures" / "scopes"


def load(name):
    return json.loads((FIXTURES / f"{name}-2026-09-15.json").read_text())


def all_nodes(nodes):
    for node in nodes:
        yield node
        yield from all_nodes(node.get("children", []))


@pytest.mark.parametrize(
    "name,markers",
    [
        ("a", ("marketing", "social", "loyalty", "fideliz", "impres", "sme")),
        ("c", ("raccomand", "recommend", "commerc", "collaborat", "content")),
        ("b", ("dati", "lavor", "control", "data", "worker", "gdpr", "statut")),
    ],
)
def test_every_query_carries_the_topic_and_structural_nodes_are_not_searched(
    name, markers
):
    tree = load(name)
    requests, parents, _ = plan(tree["topic"], tree["nodes"])
    by_id = {n["scope_id"]: n for n in all_nodes(tree["nodes"])}
    assert requests, "the plan is empty"
    for scope_id, text in requests:
        assert any(m in text for m in markers), (by_id[scope_id]["title"], text)
        assert not is_structural(by_id[scope_id])
        assert len(text.split()) <= 12
    searched = {s for s, _ in requests}
    for node in all_nodes(tree["nodes"]):
        title = node["title"].casefold()
        if title.startswith(("introduzione", "conclusioni", "bibliografia")):
            assert node["scope_id"] not in searched, title
        if node.get("children"):
            assert node["scope_id"] not in searched, "chapters ride on sub-nodes"
            for child in node["children"]:
                assert parents[child["scope_id"]] == node["scope_id"]
    # Two queries per leaf at most, no bare titles: far fewer than 3 per node.
    assert len(requests) <= 2 * sum(
        1 for n in all_nodes(tree["nodes"]) if not n.get("children")
    )
    assert len(set(requests)) == len(requests)


def test_methodology_and_evidence_nodes_of_economics_are_searched_with_the_topic():
    tree = load("a")
    requests, _, _ = plan(tree["topic"], tree["nodes"])
    by_id = {n["scope_id"]: n for n in all_nodes(tree["nodes"])}
    texts = {by_id[s]["title"]: t for s, t in requests}
    assert any("Metodologia" in title for title in texts)
    assert any("Evidenze empiriche" in title for title in texts)
    for title, text in texts.items():
        if "Metodologia" in title:
            assert "metodologia" in text or "methodology" in text
            assert "marketing" in text or "social" in text


def test_topic_core_keeps_the_subject_and_drops_generic_words():
    assert topic_core(load("a")["topic"]) == [
        "digital",
        "marketing",
        "piccole",
        "medie",
    ]
    core = topic_core(load("c")["topic"])
    assert "raccomandazione" in core and "sistemi" not in core
    assert "tutela" in topic_core(load("b")["topic"])


def test_off_topic_candidates_of_the_economics_pack_are_dropped_before_verification():
    tree = load("a")
    _, _, pattern = plan(tree["topic"], tree["nodes"])
    kept = {
        row["title"][:40]
        for row in tree["pack_titles"]
        if on_topic({"title": row["title"], "abstract": row["abstract"]}, pattern)
    }
    dropped = {row["title"][:40] for row in tree["pack_titles"]} - kept
    for junk in (
        "Copper complexes of synthetic peptides",
        "Tortura e razzismo",
        "Lessico: insegnarlo e impararlo",
        "Valutazione della ricerca",
        "Repertori dei movimenti ecclesiali",
        "Acquisizioni della genetica",
    ):
        assert any(d.startswith(junk[:30]) for d in dropped), junk
    for good in (
        "PMI Marketing: modello di business",
        "Innovative digital marketing strateg",
        "Social media analytics: mejora de la",
        "Setting the future of digital and so",
    ):
        assert any(k.startswith(good[:30]) for k in kept), good
    assert len(dropped) >= len(tree["pack_titles"]) // 3


def test_candidates_without_a_title_never_pass_and_short_words_match_whole_words():
    pattern = anchors("Social media e customer loyalty nelle PMI")
    assert not on_topic({"title": "", "abstract": "social media"}, pattern)
    assert on_topic({"title": "Fidelizzazione via social media"}, pattern)
    assert not on_topic({"title": "Courts and medical malpractice"}, pattern)
    assert on_topic({"title": "Customer loyalty in SMEs", "abstract": None}, pattern)


def test_law_tree_keeps_its_leaf_questions():
    tree = load("b")
    requests, _, _ = plan(tree["topic"], tree["nodes"])
    leaves = [n for n in all_nodes(tree["nodes"]) if not n.get("children")]
    subject_leaves = [n for n in leaves if not is_structural(n)]
    assert {s for s, _ in requests} == {n["scope_id"] for n in subject_leaves}
