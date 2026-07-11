"""Focused tests for the shared scholarly-source identity contract."""

from dataclasses import dataclass

import pytest

from app.services.ai_pipeline.source_identity import (
    SourceIdentityConflict,
    canonical_identity_digest,
    merge_source_identities,
    source_identity,
    sources_equivalent,
)


def _source(**overrides):
    source = {
        "title": "Artificial Intelligence in Higher Education",
        "authors": ["Mario Rossi", "Anna Bianchi"],
        "year": 2023,
        "paper_id": None,
        "doi": None,
    }
    source.update(overrides)
    return source


def test_same_uploaded_id_is_strong_but_distinct_uploaded_ids_do_not_merge():
    left = _source(paper_id="uploaded:17", title="Manager copy", authors=[])
    same = _source(paper_id="uploaded:17", title="Renamed copy", year=2020)
    distinct = _source(paper_id="uploaded:18", doi="10.1234/same")
    left_with_doi = _source(paper_id="uploaded:17", doi="10.1234/same")

    assert sources_equivalent(left, same)
    assert not sources_equivalent(left_with_doi, distinct)


def test_distinct_dois_never_merge_even_when_everything_else_matches():
    left = _source(paper_id="uploaded:17", doi="https://doi.org/10.1000/ONE")
    right = _source(paper_id="uploaded:17", doi="doi:10.1000/two")

    assert not sources_equivalent(left, right)


def test_equal_normalized_doi_identifies_source_despite_metadata_drift():
    left = _source(doi="https://doi.org/10.5555/ABC", title="Short title")
    right = _source(
        doi="doi:10.5555/abc",
        title="A completely different provider title",
        authors=["Different Author"],
        year=2018,
    )

    assert sources_equivalent(left, right)


def test_metadata_fallback_normalizes_title_year_and_author_surnames():
    left = _source(
        title="L’intelligenza artificiale: nell’università!",
        authors=["Rossi, Mario", "Élodie García"],
        year=2022,
    )
    right = _source(
        title="L intelligenza artificiale nell universita",
        authors=["Anna Rossi"],
        year=2023,
    )

    assert sources_equivalent(left, right)


@pytest.mark.parametrize(
    "overrides",
    [
        {"year": 2025},
        {"authors": ["Giulia Verdi"]},
        {"authors": []},
        {"title": "A different study"},
    ],
)
def test_metadata_fallback_requires_all_three_signals(overrides):
    assert not sources_equivalent(_source(), _source(**overrides))


@dataclass
class ObjectSource:
    title: str
    authors: list[str]
    year: int
    paper_id: str | None = None
    doi: str | None = None


def test_digest_is_stable_across_mapping_and_object_representations():
    mapping = _source(
        title="Étude on AI",
        authors=["Rossi, Mario", "Anna Bianchi"],
        doi="https://doi.org/10.1000/ABC",
    )
    obj = ObjectSource(
        title="Etude on AI",
        authors=["Anna Bianchi", "Mario Rossi"],
        year=2023,
        doi="doi:10.1000/abc",
    )

    assert source_identity(mapping) == source_identity(obj)
    assert canonical_identity_digest(mapping) == canonical_identity_digest(obj)
    assert len(canonical_identity_digest(mapping)) == 64


def test_merge_is_commutative_and_combines_identity_evidence():
    left = _source(
        title="AI in Education",
        authors=["Mario Rossi"],
        year=2022,
        doi="10.1000/ai",
    )
    right = _source(
        title="Artificial Intelligence in Education",
        authors=["Rossi, Mario", "Anna Bianchi"],
        year=2023,
        doi="https://doi.org/10.1000/AI",
    )

    merged = merge_source_identities(left, right)

    assert merged == merge_source_identities(right, left)
    assert merged.doi == "10.1000/ai"
    assert merged.title == "artificial intelligence in education"
    assert merged.year == 2022
    assert merged.author_surnames == ("bianchi", "rossi")


def test_merge_rejects_non_equivalent_sources():
    with pytest.raises(SourceIdentityConflict):
        merge_source_identities(
            _source(doi="10.1000/one"),
            _source(doi="10.1000/two"),
        )
