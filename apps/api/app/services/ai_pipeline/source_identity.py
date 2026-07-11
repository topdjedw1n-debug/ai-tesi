"""Deterministic identity rules for scholarly sources.

The pipeline sees the same publication through several representations:
retrieval DTOs, persisted ORM rows, uploaded files, and canonical metadata
returned by verification providers.  This module deliberately accepts both
objects and mappings so every stage can apply one identity contract.

Identity priority is:

1. matching manager-uploaded ``paper_id`` values (``uploaded:...``),
2. matching normalized DOIs when both sides have one,
3. normalized title, publication year within one year, and at least one
   overlapping normalized author surname.

Conflicting strong identifiers are vetoes: distinct uploaded IDs do not
merge, and distinct non-empty DOIs never merge even when all other metadata
looks identical.
"""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

YEAR_TOLERANCE = 1

_DOI_URL_PREFIXES = (
    "https://doi.org/",
    "http://doi.org/",
    "https://dx.doi.org/",
    "http://dx.doi.org/",
    "doi:",
)


class SourceIdentityConflict(ValueError):
    """Raised when callers try to merge records for different sources."""


@dataclass(frozen=True, slots=True)
class SourceIdentity:
    """Normalized, transport-independent identity fields for one source."""

    uploaded_paper_id: str | None
    doi: str | None
    title: str
    year: int | None
    author_surnames: tuple[str, ...]

    def canonical_payload(self) -> dict[str, Any]:
        """Return the stable payload used for contracts and pack digests."""
        return {
            "uploaded_paper_id": self.uploaded_paper_id,
            "doi": self.doi,
            "title": self.title,
            "year": self.year,
            "author_surnames": list(self.author_surnames),
        }

    def digest(self) -> str:
        """Return a stable SHA-256 digest of all normalized identity fields."""
        encoded = json.dumps(
            self.canonical_payload(),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()


def normalize_title(title: str | None) -> str:
    """Fold accents/case/punctuation while preserving non-Latin letters."""
    if not title:
        return ""
    normalized = unicodedata.normalize("NFKD", str(title))
    normalized = "".join(char for char in normalized if not unicodedata.combining(char))
    normalized = normalized.casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return re.sub(r"\s+", " ", normalized).strip()


def normalize_doi(doi: str | None) -> str | None:
    """Normalize DOI URLs/prefixes; reject values that are not DOI-like."""
    if not doi:
        return None
    normalized = str(doi).strip().casefold()
    for prefix in _DOI_URL_PREFIXES:
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
            break
    normalized = normalized.strip()
    return normalized if normalized.startswith("10.") else None


def uploaded_paper_id(paper_id: str | None) -> str | None:
    """Return a manager-upload ID, preserving its exact case-sensitive value."""
    if not paper_id:
        return None
    value = str(paper_id).strip()
    return value if value.casefold().startswith("uploaded:") else None


def normalized_author_surnames(authors: Any) -> tuple[str, ...]:
    """Return sorted unique, accent-folded author surnames."""
    surnames: set[str] = set()
    for author in authors or []:
        if isinstance(author, Mapping):
            author = author.get("name") or author.get("display_name") or ""
        value = str(author or "").strip()
        if not value:
            continue
        surname = value.split(",", 1)[0] if "," in value else value.split()[-1]
        normalized = normalize_title(surname).replace(" ", "")
        if normalized:
            surnames.add(normalized)
    return tuple(sorted(surnames))


def _field(source: Mapping[str, Any] | object, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _year(value: Any) -> int | None:
    try:
        year = int(value)
    except (TypeError, ValueError):
        return None
    return year if year > 0 else None


def source_identity(source: Mapping[str, Any] | object) -> SourceIdentity:
    """Build a normalized identity from a DTO, ORM row, dataclass, or mapping."""
    return SourceIdentity(
        uploaded_paper_id=uploaded_paper_id(_field(source, "paper_id")),
        doi=normalize_doi(_field(source, "doi")),
        title=normalize_title(_field(source, "title")),
        year=_year(_field(source, "year")),
        author_surnames=normalized_author_surnames(_field(source, "authors", [])),
    )


def canonical_identity_digest(source: Mapping[str, Any] | object) -> str:
    """Return the canonical digest identity used in frozen source-pack hashes."""
    return source_identity(source).digest()


def sources_equivalent(
    left: Mapping[str, Any] | object,
    right: Mapping[str, Any] | object,
) -> bool:
    """Return whether two records identify the same scholarly source."""
    a = source_identity(left)
    b = source_identity(right)

    # DOI disagreement is an absolute veto, even if an upload ID matches.
    if a.doi and b.doi and a.doi != b.doi:
        return False

    # Uploaded IDs are strong and exact.  Two different uploaded files remain
    # separate even if a provider happens to assign them the same DOI.
    if a.uploaded_paper_id and b.uploaded_paper_id:
        return a.uploaded_paper_id == b.uploaded_paper_id

    if a.doi and b.doi:
        return a.doi == b.doi

    if not a.title or a.title != b.title:
        return False
    if a.year is None or b.year is None or abs(a.year - b.year) > YEAR_TOLERANCE:
        return False
    if not a.author_surnames or not b.author_surnames:
        return False
    return bool(set(a.author_surnames) & set(b.author_surnames))


def merge_source_identities(
    left: Mapping[str, Any] | object,
    right: Mapping[str, Any] | object,
) -> SourceIdentity:
    """Return one deterministic identity for two equivalent source records.

    The result is commutative: argument order cannot change it.  When strong
    identifiers establish equivalence despite metadata drift, the more
    informative normalized title is retained, the earlier plausible year is
    used (online-first publications commonly precede print by one year), and
    author surnames are combined.
    """
    if not sources_equivalent(left, right):
        raise SourceIdentityConflict("Cannot merge non-equivalent source records")

    a = source_identity(left)
    b = source_identity(right)
    titles = [title for title in (a.title, b.title) if title]
    title = max(titles, key=lambda value: (len(value), value)) if titles else ""
    years = [year for year in (a.year, b.year) if year is not None]

    return SourceIdentity(
        uploaded_paper_id=a.uploaded_paper_id or b.uploaded_paper_id,
        doi=a.doi or b.doi,
        title=title,
        year=min(years) if years else None,
        author_surnames=tuple(sorted(set(a.author_surnames) | set(b.author_surnames))),
    )


__all__ = [
    "SourceIdentity",
    "SourceIdentityConflict",
    "YEAR_TOLERANCE",
    "canonical_identity_digest",
    "merge_source_identities",
    "normalize_doi",
    "normalize_title",
    "normalized_author_surnames",
    "source_identity",
    "sources_equivalent",
    "uploaded_paper_id",
]
