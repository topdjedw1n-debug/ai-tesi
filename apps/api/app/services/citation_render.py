"""Render pack markers into readable citations; legal sources by their label.

Reviewer feedback 14.09.2026: judgments and statutes must be cited by the
specific decision or act, not by an institution; page locators belong inside
the parentheses; bibliography entries need real fields. This module is pure
text: the executor's S5 owns verification and warnings.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.services.ai_pipeline.citation_formatter import (
    CitationFormatter,
    SourceDocument,
)

LEGAL_AUTHORS = re.compile(
    r"\b(?:Corte|Cassazione|Tribunale|Consiglio di Stato|Garante|Repubblica|"
    r"Parlamento|Commissione|Consiglio dell|Court|Parliament|Commission|"
    r"Autorità|Autorita)\b",
    re.I,
)
LEGAL_TITLES = re.compile(
    r"^\s*(?:Legge|L\.|Decreto|D\.\s?Lgs\.?|D\.\s?L\.|D\.P\.R\.|Regolamento|"
    r"Direttiva|Regulation|Directive|Cass\.|Corte|Sentenza|Ordinanza|"
    r"Provvedimento|Linee guida|Statuto|Codice|Tribunale|Consiglio di Stato|"
    r"Garante|Case of|Judgment|[A-ZÀ-Ý][\w' .-]+ v\. )",
    re.I,
)
PAGE_LOCATOR = re.compile(r"\s*,?\s*(pp?)\.\s*(\d+(?:\s*[-–]\s*\d+)?)")
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")


def is_legal_source(source: Any) -> bool:
    authors = " ".join(getattr(source, "authors", None) or [])
    title = str(getattr(source, "title", "") or "")
    return bool(LEGAL_AUTHORS.search(authors)) or bool(LEGAL_TITLES.match(title))


def legal_label(title: str) -> str:
    """The specific act or decision as the manager named it, without asides."""
    label = str(title or "").split(" (", 1)[0]
    label = re.sub(r",\s*testo vigente\s*$", "", label, flags=re.I)
    label = " ".join(label.split()).rstrip(" .,;")
    return label[:120]


def sentence_at(text: str, marker: str) -> str:
    return next((s.strip() for s in SENTENCE_SPLIT.split(text) if marker in s), marker)


def sort_key(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value)
    return "".join(c for c in folded if not unicodedata.combining(c)).casefold()


def with_locator(citation: str, label: str, value: str) -> str:
    """Put "p. 12" or "pp. 3-5" inside the parentheses of a citation."""
    value = re.sub(r"\s*[-–]\s*", "–", value)
    if citation.endswith(")"):
        return f"{citation[:-1]}, {label}. {value})"
    return f"{citation} ({label}. {value})"


def render_citations(
    text: str, known: dict[str, Any], style: Any, marker: re.Pattern[str]
) -> tuple[str, dict[str, dict[str, Any]], list[tuple[str, str]]]:
    """Replace every [KEY] (with an optional trailing page locator) by its
    citation; return the text, the bibliography entries used and the keys the
    pack does not know (marker removed, sentence kept for the warning)."""
    entries: dict[str, dict[str, Any]] = {}
    missing: list[tuple[str, str]] = []
    for key in dict.fromkeys(marker.findall(text)):
        source = known.get(key)
        bracket = f"[{key}]"
        if source is None:
            missing.append((key, sentence_at(text, bracket)))
            text = text.replace(bracket, "")
            continue
        meta = source.canonical_metadata or {}
        legal = is_legal_source(source)
        if legal:
            citation = f"({legal_label(source.title)})"
            formatted = f"{source.title.strip().rstrip('.')}."
            if source.url:
                formatted += f" {source.url}"
        else:
            authors = source.authors or [source.title]
            formatted = CitationFormatter.format_reference(
                SourceDocument(
                    title=source.title,
                    authors=authors,
                    year=source.year,
                    journal=source.venue,
                    doi=source.doi,
                    url=source.url,
                ),
                style=style,
            )
            citation = CitationFormatter.format_intext(
                authors, source.year, style=style
            )

        def replace(match, citation=citation):
            if match.group(1):
                return with_locator(citation, match.group(1), match.group(2))
            return citation

        text = re.sub(
            re.escape(bracket) + "(?:" + PAGE_LOCATOR.pattern + ")?",
            replace,
            text,
        )
        entries[key] = {
            "key": key,
            "formatted": formatted,
            "verified": True,
            "verification_provider": meta["verification_provider"],
            "origin": meta.get("origin", "pack"),
            "kind": "legal" if legal else "academic",
            "sort_key": sort_key(formatted),
        }
    return text, entries, missing


QUOTED_CITATION = re.compile(r"«[^»]{20,}»\s*\(([^)]*)\)")


def quotes_without_page(text: str) -> int:
    """Direct quotations whose citation carries no page locator."""
    return sum(
        1
        for m in QUOTED_CITATION.finditer(text)
        if not re.search(r"\bpp?\.\s*\d", m.group(1))
    )


def suspect_metadata(source: Any, year_now: int) -> list[str]:
    """Bibliography fields a reviewer would reject; the executor only warns."""
    reasons = []
    year = getattr(source, "year", None)
    if not year:
        reasons.append("рік відсутній")
    elif int(year) > year_now:
        reasons.append(f"рік {year} у майбутньому")
    if not is_legal_source(source) and not (getattr(source, "authors", None) or []):
        reasons.append("автори відсутні")
    if len(str(getattr(source, "title", "") or "").strip()) < 8:
        reasons.append("назва неповна")
    return reasons


def pages_out_of_range(raw: str, marker: Any, page_counts: dict[str, int]) -> list[str]:
    """Locators beyond the document's last page: a page borrowed from another
    document (B, 14.09: an order of six pages cited at p. 17 and p. 20)."""
    found = []
    pattern = re.compile(
        r"\[(" + "|".join(map(re.escape, page_counts)) + r")\]" + PAGE_LOCATOR.pattern
    )
    if not page_counts:
        return found
    for match in pattern.finditer(raw):
        key, pages = match.group(1), match.group(3)
        last = max(int(n) for n in re.findall(r"\d+", pages))
        if last > page_counts[key]:
            found.append(f"{key} p. {last} > {page_counts[key]}")
    return found


def library_sources(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Verified standard-library rows as citable sources."""
    from app.services.ai_pipeline.rag_retriever import SourceDoc

    known: dict[str, Any] = {}
    for row in rows:
        if row.get("verification_status") != "verified":
            continue
        source = SourceDoc(**row["source"])
        source.canonical_metadata = {
            **(source.canonical_metadata or {}),
            "verification_provider": row["verification_provider"],
            "origin": "library",
        }
        known[row["key"]] = source
    return known


def suspect_entries(keys: Any, known: dict[str, Any], year: int) -> list[str]:
    return [
        f"{key}: {', '.join(reasons)}"
        for key in keys
        if (reasons := suspect_metadata(known[key], year))
    ]


def page_counts(pack: Any) -> dict[str, int]:
    """Last page number of every full-text document in the pack."""
    counts: dict[str, int] = {}
    for passage in getattr(pack, "passages", None) or []:
        counts[passage.citation_key] = max(
            counts.get(passage.citation_key, 0), passage.page_number
        )
    return counts
