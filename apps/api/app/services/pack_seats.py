"""Seats of the source pack: which verified candidates the pack keeps and
which plan nodes each of them covers.

A node is covered only by a record whose title or abstract carries the node's
own terms (``material_fit.covers``); the query that found the record stays
recorded as history. The node's reserved seats go to such records first,
those with the most own terms first; the rest of the pack fills in the order
the candidates were found, as before.
"""

from __future__ import annotations

from typing import Any

from app.services.material_fit import covers, document_text
from app.services.search_queries import is_structural
from app.services.source_evidence import evidence_text


def tag_scopes(
    text: str, nodes: list[dict[str, Any]], parents: dict[str, str]
) -> dict[str, int]:
    """Own-term matches per subject node, chapters credited through their
    matched sub-nodes (a chapter's own terms count too)."""
    found: dict[str, int] = {}
    for node in nodes:
        hits = covers(node, text)
        if hits:
            found[node["scope_id"]] = hits
    for scope_id in list(found):
        parent = parents.get(scope_id)
        while parent and parent not in found:
            found[parent] = 0
            parent = parents.get(parent)
    return found


def identity(source: Any) -> str:
    doi = getattr(source, "doi", None)
    return str(doi or getattr(source, "title", "")).strip().casefold()


def seat(
    rows: list[Any],
    nodes: list[dict[str, Any]],
    *,
    minimum: int,
    max_sources: int,
) -> tuple[list[Any], dict[str, int]]:
    """Keep at most ``max_sources`` rows: for every subject node, up to
    ``minimum`` rows that carry the node's own terms and have readable text
    (most own terms first), then the remaining rows in their original order.
    Returns the selection and the coverage (rows with text per node)."""
    selected: list[Any] = []
    seen: set[str] = set()

    def add(row: Any) -> None:
        key = identity(row.source)
        if key not in seen and len(selected) < max_sources:
            selected.append(row)
            seen.add(key)

    def tags(row: Any) -> dict[str, int]:
        return dict((row.source.canonical_metadata or {}).get("scope_hits") or {})

    order = {id(row): position for position, row in enumerate(rows)}
    for node in nodes:
        if is_structural(node):
            continue
        matches = [
            row
            for row in rows
            if node["scope_id"] in tags(row) and evidence_text(row.source)
        ]
        matches.sort(key=lambda r: (-tags(r)[node["scope_id"]], order[id(r)]))
        for row in matches[:minimum]:
            add(row)
    # The remaining seats: records the system can read (an open-access link)
    # before the others, each in the order the catalogues returned them.
    readable = [
        row
        for row in rows
        if (row.source.canonical_metadata or {}).get("open_access_url")
    ]
    for row in readable + rows:
        add(row)
    coverage = {
        node["scope_id"]: sum(
            1
            for row in selected
            if node["scope_id"] in tags(row) and evidence_text(row.source)
        )
        for node in nodes
        if not is_structural(node)
    }
    return selected, coverage


def scope_metadata(
    source: Any,
    nodes: list[dict[str, Any]],
    parents: dict[str, str],
    text: str | None = None,
) -> dict[str, Any]:
    """The scope fields of a source's canonical metadata from its own text."""
    hits = tag_scopes(
        text if text is not None else document_text(source), nodes, parents
    )
    return {"scope_ids": sorted(hits), "scope_hits": hits}
