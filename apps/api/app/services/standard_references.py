"""Render model-supplied standard references, retaining their unverified origin."""

import json
import re

from app.services.ai_pipeline.citation_formatter import (
    CitationFormatter,
    SourceDocument,
)

STANDARD_SOURCE_RULES = """
SOURCE RULES FOR THIS JOB:
Write the requested subject matter using appropriate academic sources. The
retrieved pack is useful evidence, not the complete universe of legitimate sources.
For definitions, established taxonomies, standard frameworks and guidelines,
you may cite standard textbooks, official manuals and guidelines outside the pack
(e.g. NANDA-I or WHO when relevant). Use an identifiable standard source you know;
never invent a DOI, page number, edition, year, quotation or verification claim.
Never invent numeric data or study findings. Attribute statistics only to
available source evidence; use concrete qualitative findings when numbers are absent.
For retrieved pack sources use their exact [Key]. For a standard source outside
the pack use [STD:identifier] and list its bibliographic details in a final block:
<STANDARD_REFERENCES_JSON>
[{"id":"identifier","title":"Exact known title","authors":["Author or institution"],"year":null}]
</STANDARD_REFERENCES_JSON>
Use null for an unknown year. Include only standard sources actually cited.
This block is metadata for the application and is removed from the work; do not
put verification labels or application instructions in the prose. Do not present
model recall as a retrieved study result or as a verified passage. State limitations
where specific evidence is unavailable, while still covering the agreed subsections.
"""


def render_standard_references(content, style):
    """Return prose, bibliography and explicit manager-verification records."""
    tag = "<STANDARD_REFERENCES_JSON>"
    if tag not in content:
        prose, metadata = content, "[]"
    else:
        prose, metadata = content.split(tag, 1)
    records, bibliography = [], []
    try:
        metadata = metadata.split("</STANDARD_REFERENCES_JSON>", 1)[0].strip()
        metadata = re.sub(r"^```(?:json)?\s*|\s*```$", "", metadata, flags=re.I)
        raw = json.loads(metadata)
        if not isinstance(raw, list):
            raise ValueError("Standard references must be a list")
    except (ValueError, TypeError):
        raw = []
        records.append(
            {
                "status": "manager_verification_required",
                "issue": "Malformed standard-reference metadata",
            }
        )
    seen = set()
    for item in raw:
        if not isinstance(item, dict):
            continue
        identifier, title, authors = (
            item.get("id"),
            item.get("title"),
            item.get("authors"),
        )
        if (
            not isinstance(identifier, str)
            or identifier in seen
            or not re.fullmatch(r"[A-Za-z0-9_-]+", identifier)
        ):
            continue
        marker = f"[STD:{identifier}]"
        if marker not in prose:
            continue
        if (
            not isinstance(title, str)
            or not title.strip()
            or not isinstance(authors, list)
            or not authors
            or not all(isinstance(a, str) and a.strip() for a in authors)
        ):
            records.append(
                {
                    "id": identifier,
                    "status": "manager_verification_required",
                    "issue": "Incomplete standard-reference metadata",
                }
            )
            continue
        seen.add(identifier)
        year = item.get("year")
        year = (
            year
            if isinstance(year, int)
            and not isinstance(year, bool)
            and 1000 <= year <= 2100
            else None
        )
        if year is not None:
            citation = CitationFormatter.format_intext(authors, year, style=style)
            reference = CitationFormatter.format_reference(
                SourceDocument(title=title, authors=authors, year=year), style=style
            )
        else:
            citation = "(" + "; ".join(authors) + ", s.d.)"
            reference = "; ".join(authors) + ". (s.d.). " + title + "."
        prose = prose.replace(marker, citation)
        bibliography.append(reference)
        records.append(
            {
                "id": identifier,
                "title": title,
                "authors": authors,
                "year": year,
                "origin": "model_standard_reference",
                "status": "manager_verification_required",
                "in_frozen_pack": False,
                "identity_verified": False,
            }
        )
    unresolved = re.findall(r"\[STD:([^\]]+)\]", prose)
    if unresolved:
        records.append(
            {
                "status": "manager_verification_required",
                "issue": "Unresolved standard-reference identifiers",
                "ids": unresolved,
            }
        )
        # Keep the model's label, without inventing bibliographic metadata or
        # exposing a transport marker in a work. The manager sees the issue.
        prose = re.sub(
            r"\[STD:([^\]]+)\]", lambda match: "(" + match.group(1) + ", s.d.)", prose
        )
    return prose.rstrip(), bibliography, records
