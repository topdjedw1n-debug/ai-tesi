"""
Unit tests for CitationFreezer (freeze/restore/verify).
"""

from app.services.ai_pipeline.citation_freezer import CitationFreezer


def test_freeze_and_restore_roundtrips_citations():
    text = "Neural nets scale well [Vaswani et al., 2017] on large corpora."
    frozen, mapping = CitationFreezer.freeze(text)

    assert "[Vaswani et al., 2017]" not in frozen
    assert "⟦C1⟧" in frozen
    assert mapping["⟦C1⟧"] == "[Vaswani et al., 2017]"
    assert CitationFreezer.restore(frozen, mapping) == text


def test_two_citations_back_to_back():
    text = "As shown [Smith, 2020][Jones, 2021] the effect holds."
    frozen, mapping = CitationFreezer.freeze(text)

    assert len(mapping) == 2
    assert "⟦C1⟧⟦C2⟧" in frozen
    assert CitationFreezer.restore(frozen, mapping) == text


def test_citation_at_end_of_sentence():
    text = "The result is significant [Rossi, 2019]."
    frozen, mapping = CitationFreezer.freeze(text)

    # The trailing period stays in the prose, only the marker is frozen.
    assert frozen.endswith("⟦C1⟧.")
    assert CitationFreezer.restore(frozen, mapping) == text


def test_long_quote_is_frozen():
    quote = (
        "“the medium is the message and this reshapes how societies come to "
        "understand themselves over time”"
    )
    text = f"McLuhan argued that {quote} in his later work."
    frozen, mapping = CitationFreezer.freeze(text)

    assert quote not in frozen
    assert "⟦Q1⟧" in frozen
    assert CitationFreezer.restore(frozen, mapping) == text


def test_short_quote_left_in_prose():
    # A scare-quoted term (< 10 words) must stay so the sentence can be
    # smoothed around it.
    text = "The so-called “digital divide” persists across regions."
    frozen, mapping = CitationFreezer.freeze(text)

    assert mapping == {}
    assert "“digital divide”" in frozen


def test_guillemet_quote_frozen_italian():
    quote = (
        "«la lingua è il fondamento stesso di ogni comunità che intende "
        "riconoscersi come tale nel tempo»"
    )
    text = f"Come nota l'autore, {quote}, secondo la tradizione."
    frozen, mapping = CitationFreezer.freeze(text)

    assert quote not in frozen
    assert CitationFreezer.restore(frozen, mapping) == text


def test_all_present_detects_dropped_placeholder():
    text = "Point one [A, 2001] and point two [B, 2002]."
    frozen, mapping = CitationFreezer.freeze(text)

    good_rewrite = frozen.replace("Point", "Argument")
    assert CitationFreezer.all_present(good_rewrite, mapping)

    # Model silently ate the second marker.
    bad_rewrite = good_rewrite.replace("⟦C2⟧", "")
    assert not CitationFreezer.all_present(bad_rewrite, mapping)


def test_no_citations_is_noop():
    text = "A plain paragraph with no markers or quotations at all."
    frozen, mapping = CitationFreezer.freeze(text)

    assert frozen == text
    assert mapping == {}
    assert CitationFreezer.all_present(frozen, mapping)
