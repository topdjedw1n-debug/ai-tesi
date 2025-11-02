"""
Citation formatter for APA, MLA, and Chicago styles
Handles both in-text citations and bibliography/reference formatting
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class CitationStyle(str, Enum):
    """Supported citation styles"""

    APA = "apa"
    MLA = "mla"
    CHICAGO = "chicago"


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
            return CitationFormatter._format_apa_intext(authors, year, page)
        elif style == CitationStyle.MLA:
            return CitationFormatter._format_mla_intext(authors, year, page)
        elif style == CitationStyle.CHICAGO:
            return CitationFormatter._format_chicago_intext(authors, year, page)
        else:
            raise ValueError(f"Unsupported citation style: {style}")

    @staticmethod
    def format_reference(
        source: SourceDocument, style: CitationStyle = CitationStyle.APA
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
            return CitationFormatter._format_apa_reference(source)
        elif style == CitationStyle.MLA:
            return CitationFormatter._format_mla_reference(source)
        elif style == CitationStyle.CHICAGO:
            return CitationFormatter._format_chicago_reference(source)
        else:
            raise ValueError(f"Unsupported citation style: {style}")

    @staticmethod
    def _format_apa_intext(
        authors: list[str], year: int, page: int | None = None
    ) -> str:
        """Format APA in-text citation"""
        if len(authors) == 1:
            citation = f"{authors[0]}, {year}"
        elif len(authors) == 2:
            citation = f"{authors[0]} & {authors[1]}, {year}"
        else:
            citation = f"{authors[0]} et al., {year}"

        if page:
            citation += f", p. {page}"

        return f"({citation})"

    @staticmethod
    def _format_mla_intext(
        authors: list[str], year: int, page: int | None = None
    ) -> str:
        """Format MLA in-text citation"""
        if len(authors) == 1:
            citation = authors[0]
        elif len(authors) == 2:
            citation = f"{authors[0]} and {authors[1]}"
        else:
            citation = f"{authors[0]} et al."

        if page:
            citation += f" {page}"

        return f"({citation})"

    @staticmethod
    def _format_chicago_intext(
        authors: list[str], year: int, page: int | None = None
    ) -> str:
        """Format Chicago in-text citation (notes-bibliography style)"""
        if len(authors) == 1:
            citation = authors[0]
        elif len(authors) == 2:
            citation = f"{authors[0]} and {authors[1]}"
        else:
            citation = f"{authors[0]} et al."

        citation += f", {year}"

        if page:
            citation += f", {page}"

        return f"({citation})"

    @staticmethod
    def _format_apa_reference(source: SourceDocument) -> str:
        """Format APA reference"""
        # Author list
        if len(source.authors) == 1:
            authors = f"{source.authors[0]}"
        elif len(source.authors) <= 7:
            authors = ", ".join(source.authors[:-1]) + f", & {source.authors[-1]}"
        else:
            authors = ", ".join(source.authors[:6]) + ", ... " + source.authors[-1]

        # Year
        year_str = f" ({source.year})."

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
    def _format_chicago_reference(source: SourceDocument) -> str:
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
                reference += f" ({source.year})"
            if source.pages:
                reference += f": {source.pages}"
        else:
            reference = f"{authors}. {title_str}"
            if source.publisher:
                reference += f" {source.publisher}"
            if source.city:
                reference += f", {source.city}"
            if source.year:
                reference += f", {source.year}"

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
        # Pattern: [Author, Year] or [Author et al., Year]
        pattern = r"\[([^\]]+),\s*(\d{4})\]"

        for match in re.finditer(pattern, text):
            citation_str = match.group(1)
            year = int(match.group(2))

            # Parse authors (handle "et al.")
            if "et al." in citation_str:
                authors = [citation_str.replace(" et al.", "").strip()]
                et_al = True
            else:
                authors = [a.strip() for a in citation_str.split(" & ")]
                authors = [a.strip() for author in authors for a in author.split(",")]
                et_al = False

            citations.append(
                {
                    "authors": authors,
                    "year": year,
                    "et_al": et_al,
                    "original": match.group(0),
                    "position": match.start(),
                }
            )

        return citations
