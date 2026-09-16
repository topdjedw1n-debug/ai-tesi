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
from app.services.legal_sources import (  # noqa: F401 (re-exported)
    LEGAL_AUTHORS,
    LEGAL_TITLES,
    STATUTE_TITLES,
    is_legal_source,
)

PAGE_LOCATOR = re.compile(r"\s*,?\s*(pp?)\.\s*(\d+(?:\s*[-–]\s*\d+)?)")
ARTICLE_LOCATOR = re.compile(
    r"\s*,?\s*(art(?:t)?\.\s*\d+(?:[\s-]*[a-z](?:ies|er|ter|quater)?)?(?:,\s*comm[ai]\s*\d+(?:\s*e\s*\d+)?)?)",
    re.I,
)
SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
# "(UE) 2016/679" belongs to the official name; "(Statuto dei lavoratori)" and
# "(GDPR)" are asides that start the manager's notes.
ASIDE = re.compile(r" \((?!(?:UE|CE|CEE|EU|EC|Euratom)\)\s*\d)", re.I)
ORDINAL = r"(?:[\s-]*(?:bis|ter|quater|quinquies|sexies|septies|octies|novies|decies))?"
ARTICLE = re.compile(r"artt?\.\s*(\d+" + ORDINAL + ")", re.I)
OWN_ARTICLE = re.compile(r",?\s*artt?\.\s*\d+" + ORDINAL + r"\s*$", re.I)
AMENDED = re.compile(
    r"\(Modific\w*\s+all['’]\s*art(?:icolo|\.)\s*(\d+"
    + ORDINAL
    + r")\s+(?:del|della|dello|al|alla|allo)\s+([^()]+?)\s*\)",
    re.I,
)


def legal_label(title: str) -> str:
    """The specific act or decision as the manager named it, without asides."""
    label = ASIDE.split(" ".join(str(title or "").split()), 1)[0]
    label = re.sub(r",\s*testo vigente\s*$", "", label, flags=re.I)
    return label.rstrip(" .,;")[:120]


def article_number(text: str) -> str | None:
    match = ARTICLE.search(text)
    return re.sub(r"[\s-]+", "-", match.group(1)).lower() if match else None


def legal_citation(label: str, title: str, locator: str) -> str:
    """An article locator on an act the manager named by one of its articles.

    The same article ("art. 23, comma 1" on "…, n. 151, art. 23") is one
    reference, not two. The article of the act it amends, declared in the
    title as "(Modifiche all'articolo 4 della legge …, n. 300)", is cited as
    that act's article as amended. Any other pairing stays as written: the
    amending act's article and the amended act's article are different
    references and are never merged mechanically."""
    own = OWN_ARTICLE.search(label)
    number = article_number(locator)
    if own and number == article_number(own.group(0)):
        return f"({label}{locator[ARTICLE.search(locator).end():]})"
    amended = AMENDED.search(title)
    if own and amended and number == article_number("art. " + amended.group(1)):
        act = amended.group(2).strip().rstrip(" .,;")
        return (
            f"({act[:1].upper()}{act[1:]}, {locator}, come modificato "
            f"dall'{own.group(0).strip(', ')}, {label[: own.start()]})"
        )
    return f"({label}, {locator})"


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

        statute = legal and bool(STATUTE_TITLES.match(source.title or ""))

        def replace(match, citation=citation, statute=statute, source=source):
            if match.group(3):
                if is_legal_source(source):
                    return legal_citation(
                        citation[1:-1], source.title, match.group(3).strip()
                    )
                return f"{citation[:-1]}, {match.group(3).strip()})"
            if match.group(1) and not statute:
                return with_locator(citation, match.group(1), match.group(2))
            return citation

        text = re.sub(
            re.escape(bracket)
            + "(?:"
            + PAGE_LOCATOR.pattern
            + ")?(?:"
            + ARTICLE_LOCATOR.pattern
            + ")?",
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
        if not re.search(r"\b(?:pp?|artt?)\.\s*\d", m.group(1))
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


def quoted_share(text: str) -> float:
    """Share of the words inside «…» quotation marks."""
    words = max(1, len(text.split()))
    quoted = sum(len(m.split()) for m in re.findall(r"«([^»]{1,800})»", text))
    return quoted / words


BARE_KEY = re.compile(r"(?<![\w\[])K[0-9a-f]{12}(?![\w\]])")
DECISION = re.compile(r"\bn\.\s*(\d{3,6})\b")
YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
SLASHED = re.compile(r"\b(\d{3,6})/((?:19|20)\d{2})\b")


def decision_years(known: dict[str, Any]) -> dict[str, str]:
    """Decision number -> year, from the titles of the legal sources."""
    years: dict[str, str] = {}
    for source in known.values():
        title = str(getattr(source, "title", "") or "")
        if not is_legal_source(source):
            continue
        number, year = DECISION.search(title), YEAR.search(title)
        if number and year:
            years[number.group(1)] = year.group(0)
    return years


def section_issues(
    section: dict[str, Any],
    text: str,
    marker: Any,
    pages: dict[str, int],
    known: dict[str, Any],
    quote_limit: float,
) -> tuple[str, dict[str, Any]]:
    """Text with bare pack keys removed, plus the advisory findings of S5:
    per-work lists (quotes without page, quoted share) and per-section
    warnings as (code, detail) pairs."""
    raw, index = section["raw_content"], section["section_index"]
    bare = sorted(set(BARE_KEY.findall(text)))
    for key in bare:
        text = re.sub(r"\s*\(?" + re.escape(key) + r"\)?", "", text)
    years = decision_years(known)
    mismatched = sorted(
        {
            f"n. {n}/{y} (fonte: {years[n]})"
            for n, y in SLASHED.findall(text)
            if n in years and years[n] != y
        }
    )
    unpaged = quotes_without_page(text)
    share = quoted_share(text)
    warnings = [
        (code, "; ".join(found))
        for code, found in (
            ("page_out_of_range", pages_out_of_range(raw, marker, pages)),
            ("citation_unresolved", bare),
            ("decision_year_mismatch", mismatched),
        )
        if found
    ]
    return text, {
        "unpaged": [f"§{index}: {unpaged}"] if unpaged else [],
        "quoted": [f"§{index}: {round(100 * share)} %"] if share > quote_limit else [],
        "warnings": warnings,
    }
