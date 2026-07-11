"""
Citation formatter for APA, MLA, and Chicago styles
Handles both in-text citations and bibliography/reference formatting
"""

from collections.abc import Iterable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class CitationStyle(StrEnum):
    """Supported citation styles"""

    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"
    HARVARD = "harvard"


@dataclass
class SourceDocument:
    """Represents a source document for citation"""

    title: str
    authors: list[str]
    year: int
    journal: str | None = None
    volume: str | None = None
    issue: str | None = None
    pages: str | None = None
    doi: str | None = None
    url: str | None = None
    publisher: str | None = None
    city: str | None = None

    def __post_init__(self) -> None:
        """Validate required fields"""
        if not self.authors:
            raise ValueError("SourceDocument must have at least one author")
        if not self.year:
            raise ValueError("SourceDocument must have a year")


class CitationFormatter:
    """Format citations in APA, MLA, or Chicago style"""

    @staticmethod
    def format_intext(
        authors: list[str],
        year: int,
        style: CitationStyle = CitationStyle.APA,
        page: int | None = None,
        year_suffix: str = "",
        disambiguation_title: str | None = None,
    ) -> str:
        """
        Format in-text citation

        Args:
            authors: List of author names
            year: Publication year
            style: Citation style
            page: Optional page number

        Returns:
            Formatted in-text citation string
        """
        if style == CitationStyle.APA:
            return CitationFormatter._format_apa_intext(
                authors, year, page, year_suffix
            )
        elif style == CitationStyle.MLA:
            return CitationFormatter._format_mla_intext(
                authors,
                year,
                page,
                disambiguation_title,
            )
        elif style == CitationStyle.CHICAGO:
            return CitationFormatter._format_chicago_intext(
                authors,
                year,
                page,
                year_suffix,
            )
        elif style == CitationStyle.HARVARD:
            return CitationFormatter._format_harvard_intext(
                authors,
                year,
                page,
                year_suffix,
            )
        else:
            raise ValueError(f"Unsupported citation style: {style}")

    @staticmethod
    def format_reference(
        source: SourceDocument,
        style: CitationStyle = CitationStyle.APA,
        year_suffix: str = "",
    ) -> str:
        """
        Format full reference for bibliography

        Args:
            source: SourceDocument instance
            style: Citation style

        Returns:
            Formatted reference string
        """
        if style == CitationStyle.APA:
            return CitationFormatter._format_apa_reference(source, year_suffix)
        elif style == CitationStyle.MLA:
            return CitationFormatter._format_mla_reference(source)
        elif style == CitationStyle.CHICAGO:
            return CitationFormatter._format_chicago_reference(source, year_suffix)
        elif style == CitationStyle.HARVARD:
            return CitationFormatter._format_harvard_reference(source, year_suffix)
        else:
            raise ValueError(f"Unsupported citation style: {style}")

    @staticmethod
    def _format_apa_intext(
        authors: list[str],
        year: int,
        page: int | None = None,
        year_suffix: str = "",
    ) -> str:
        """Format APA in-text citation"""
        surnames = [CitationFormatter._author_surname(author) for author in authors]
        if len(authors) == 1:
            citation = f"{surnames[0]}, {year}{year_suffix}"
        elif len(authors) == 2:
            citation = f"{surnames[0]} & {surnames[1]}, {year}{year_suffix}"
        else:
            citation = f"{surnames[0]} et al., {year}{year_suffix}"

        if page:
            citation += f", p. {page}"

        return f"({citation})"

    @staticmethod
    def _format_mla_intext(
        authors: list[str],
        year: int,
        page: int | None = None,
        disambiguation_title: str | None = None,
    ) -> str:
        """Format MLA in-text citation"""
        if len(authors) == 1:
            citation = authors[0]
        elif len(authors) == 2:
            citation = f"{authors[0]} and {authors[1]}"
        else:
            citation = f"{authors[0]} et al."

        if disambiguation_title:
            citation += f', "{disambiguation_title}"'

        if page:
            citation += f" {page}"

        return f"({citation})"

    @staticmethod
    def _format_chicago_intext(
        authors: list[str],
        year: int,
        page: int | None = None,
        year_suffix: str = "",
    ) -> str:
        """Format Chicago in-text citation (notes-bibliography style)"""
        if len(authors) == 1:
            citation = authors[0]
        elif len(authors) == 2:
            citation = f"{authors[0]} and {authors[1]}"
        else:
            citation = f"{authors[0]} et al."

        citation += f", {year}{year_suffix}"

        if page:
            citation += f", {page}"

        return f"({citation})"

    @staticmethod
    def _format_harvard_intext(
        authors: list[str],
        year: int,
        page: int | None = None,
        year_suffix: str = "",
    ) -> str:
        """Format Harvard in-text citation: (Author, Year) / (Author and
        Author, Year) / (Author et al., Year), pages as ', p. N'."""
        if len(authors) == 1:
            citation = authors[0]
        elif len(authors) == 2:
            citation = f"{authors[0]} and {authors[1]}"
        else:
            citation = f"{authors[0]} et al."

        citation += f", {year}{year_suffix}"

        if page:
            citation += f", p. {page}"

        return f"({citation})"

    @staticmethod
    def _format_apa_reference(source: SourceDocument, year_suffix: str = "") -> str:
        """Format APA reference"""
        formatted_authors = [
            CitationFormatter._format_apa_author(author) for author in source.authors
        ]
        # Author list
        if len(source.authors) == 1:
            authors = formatted_authors[0]
        elif len(source.authors) <= 7:
            authors = ", ".join(formatted_authors[:-1]) + f", & {formatted_authors[-1]}"
        else:
            authors = (
                ", ".join(formatted_authors[:6]) + ", ... " + formatted_authors[-1]
            )

        # Year
        year_str = f" ({source.year}{year_suffix})."

        # Title
        title_str = f" {source.title}."

        # Journal article
        if source.journal:
            reference = f"{authors}{year_str} {title_str} {source.journal}"
            if source.volume:
                reference += f", {source.volume}"
                if source.issue:
                    reference += f"({source.issue})"
            if source.pages:
                reference += f", {source.pages}"
            if source.doi:
                reference += f". https://doi.org/{source.doi}"
        else:
            # Book or other
            reference = f"{authors}{year_str} {title_str}"
            if source.publisher:
                reference += f" {source.publisher}"
            if source.city:
                reference += f". {source.city}"

        return reference

    @staticmethod
    def _author_surname(author: str) -> str:
        value = author.strip()
        if not value:
            return "Unknown"
        return value.split(",", 1)[0].strip() if "," in value else value.split()[-1]

    @staticmethod
    def _format_apa_author(author: str) -> str:
        value = author.strip()
        if not value:
            return "Unknown"
        if "," in value:
            surname, given = (part.strip() for part in value.split(",", 1))
        else:
            parts = value.split()
            if len(parts) == 1:
                return parts[0]
            surname, given = parts[-1], " ".join(parts[:-1])
        initials = " ".join(
            f"{part[0].upper()}." for part in given.replace("-", " ").split() if part
        )
        return f"{surname}, {initials}" if initials else surname

    @staticmethod
    def _format_mla_reference(source: SourceDocument) -> str:
        """Format MLA reference"""
        # Author list
        if len(source.authors) == 1:
            authors = f"{source.authors[0]}"
        elif len(source.authors) == 2:
            authors = f"{source.authors[0]}, and {source.authors[1]}"
        else:
            authors = f"{source.authors[0]}, et al."

        # Title
        title_str = f'"{source.title}."'

        # Container/publication
        if source.journal:
            reference = f"{authors}. {title_str} {source.journal}"
            if source.volume and source.issue:
                reference += f", vol. {source.volume}, no. {source.issue}"
            elif source.volume:
                reference += f", vol. {source.volume}"
            if source.year:
                reference += f", {source.year}"
            if source.pages:
                reference += f", pp. {source.pages}"
        else:
            reference = f"{authors}. {title_str}"
            if source.publisher:
                reference += f" {source.publisher}"
            if source.year:
                reference += f", {source.year}"

        return reference

    @staticmethod
    def _format_chicago_reference(
        source: SourceDocument,
        year_suffix: str = "",
    ) -> str:
        """Format Chicago reference (notes-bibliography style)"""
        # Author list
        if len(source.authors) == 1:
            authors = source.authors[0]
        elif len(source.authors) == 2:
            authors = f"{source.authors[0]} and {source.authors[1]}"
        else:
            authors = (
                f"{source.authors[0]}, {source.authors[1]}, and {source.authors[2]}"
            )

        # Title
        title_str = f'"{source.title}."'

        # Publication details
        if source.journal:
            reference = f"{authors}. {title_str} {source.journal}"
            if source.volume and source.issue:
                reference += f" {source.volume}, no. {source.issue}"
            elif source.volume:
                reference += f" {source.volume}"
            if source.year:
                reference += f" ({source.year}{year_suffix})"
            if source.pages:
                reference += f": {source.pages}"
        else:
            reference = f"{authors}. {title_str}"
            if source.publisher:
                reference += f" {source.publisher}"
            if source.city:
                reference += f", {source.city}"
            if source.year:
                reference += f", {source.year}{year_suffix}"

        return reference

    @staticmethod
    def _format_harvard_reference(
        source: SourceDocument,
        year_suffix: str = "",
    ) -> str:
        """Format Harvard reference: Author, A. and Author, B. (Year)
        'Title', Journal, Volume(Issue), pp. Pages. doi: ..."""
        if len(source.authors) == 1:
            authors = f"{source.authors[0]}"
        elif len(source.authors) == 2:
            authors = f"{source.authors[0]} and {source.authors[1]}"
        elif len(source.authors) == 3:
            authors = (
                f"{source.authors[0]}, {source.authors[1]} and {source.authors[2]}"
            )
        else:
            authors = f"{source.authors[0]} et al."

        year_str = f" ({source.year}{year_suffix})"

        if source.journal:
            reference = f"{authors}{year_str} '{source.title}', {source.journal}"
            if source.volume:
                reference += f", {source.volume}"
                if source.issue:
                    reference += f"({source.issue})"
            if source.pages:
                reference += f", pp. {source.pages}"
            reference += "."
            if source.doi:
                reference += f" doi: {source.doi}."
        else:
            # Book or other: title italicization is a rendering concern;
            # plain text here, consistent with the other formatters.
            reference = f"{authors}{year_str} {source.title}."
            if source.city and source.publisher:
                reference += f" {source.city}: {source.publisher}."
            elif source.publisher:
                reference += f" {source.publisher}."

        return reference

    @staticmethod
    def extract_citations_from_text(text: str) -> list[dict[str, Any]]:
        """
        Extract citation markers from text (e.g., [Author, Year])

        Args:
            text: Text containing citation markers

        Returns:
            List of extracted citation dictionaries
        """
        import re

        citations = []
        # Parse parenthetical/bracket groups first, then split APA multi-source
        # groups on semicolons. This avoids greedily treating
        # ``(Rossi, 2021; Bianchi, 2022)`` as one invented author string.
        group_pattern = r"[\[(]([^\]\)]+)[\])]"
        part_pattern = re.compile(
            r"\s*(.+?),\s*(\d{4})([a-z]*)(?:,\s*p\.\s*\d+)?\s*$",
            re.IGNORECASE,
        )

        for group in re.finditer(group_pattern, text):
            cursor = group.start(1)
            for raw_part in group.group(1).split(";"):
                part = raw_part.strip()
                part_match = part_pattern.fullmatch(part)
                if part_match is None:
                    cursor += len(raw_part) + 1
                    continue

                citation_str = part_match.group(1).strip()
                year = int(part_match.group(2))
                year_suffix = part_match.group(3).lower()

                et_al = "et al." in citation_str.casefold()
                if et_al:
                    authors = [
                        re.sub(
                            r"\s+et\s+al\.$",
                            "",
                            citation_str,
                            flags=re.IGNORECASE,
                        ).strip()
                    ]
                else:
                    authors = [
                        author.strip()
                        for author in re.split(r"\s+(?:&|and)\s+", citation_str)
                        if author.strip()
                    ]

                citations.append(
                    {
                        "authors": authors,
                        "year": year,
                        "year_suffix": year_suffix,
                        "et_al": et_al,
                        "original": f"{group.group(0)[0]}{part}{group.group(0)[-1]}",
                        "position": cursor,
                    }
                )
                cursor += len(raw_part) + 1

        return citations


def merge_bibliographies(per_section: Iterable[list[str] | None]) -> list[str]:
    """
    Merge per-section bibliographies into one document-level reference list.

    Dedupe by exact formatted string (the same source always formats to the
    identical string: pack keys are stable, the legacy path reuses the same
    SourceDoc), sorted alphabetically (APA convention).
    """
    seen: set[str] = set()
    merged: list[str] = []
    for section_bibliography in per_section:
        for reference in section_bibliography or []:
            cleaned = (reference or "").strip()
            if not cleaned or cleaned in seen:
                continue
            seen.add(cleaned)
            merged.append(cleaned)
    return sorted(merged, key=str.casefold)


_BIBLIOGRAPHY_HEADINGS = {
    "it": "Bibliografia",
    "en": "Bibliography",
    "uk": "Бібліографія",
}


def bibliography_heading(language: str | None) -> str:
    """Language-aware heading for the document-level reference section."""
    prefix = (language or "").lower()[:2]
    return _BIBLIOGRAPHY_HEADINGS.get(prefix, "Bibliography")
