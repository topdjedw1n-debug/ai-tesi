"""Checks on the S3 plan after the model answered: a primary document leads
every subject section, and the manager learns which material the plan needs
but the pack does not hold.

16.09.2026: the plan rules already ask for a primary source as the first key
and forbid sections that only explain; the model does not always comply
(law 15.09: three explanatory sections at 40-66 % AI; economics 16.09: a
"case studies" section written on a crowdsourcing-platform study). The
server now reorders the keys so a primary document leads, prepends one that
the search attributed to the section's scopes when the plan named none, and
warns with plan_material_gap when no primary document or no case exists for
a section that needs one. Titles stay as the manager's index gave them.
"""

import re
from typing import Any

from app.services.legal_sources import is_legal_source
from app.services.material_fit import about_section
from app.services.section_material import is_frame
from app.services.source_evidence import evidence_text

CASE_SECTION = re.compile(r"\bcas[oi]\b|\bcase stud", re.I)
CASE_SOURCE = re.compile(
    r"\bcas[oi]\b|\bcase stud|\bcase of\b|\bil caso\b|\besperienza d[ie]\b|"
    r"\bazienda\b|\bcompany\b|\bimpresa\b|\bfirm\b",
    re.I,
)


def is_primary(packed: Any, pack: Any = None, nodes: list | None = None) -> bool:
    """A document the section can be told from: full text on the topic or a
    legal act (a readable text on another subject is not primary)."""
    if is_legal_source(packed.source):
        return True
    meta = packed.source.canonical_metadata or {}
    if meta.get("evidence_level") != "pdf":
        return False
    if pack is None or not getattr(pack, "passages", None):
        return True
    from app.services.full_text_sources import full_text_usable

    return full_text_usable(pack, packed.citation_key, nodes or [])


def _scopes(packed: Any) -> set[str]:
    return set((packed.source.canonical_metadata or {}).get("scope_ids") or [])


def review(
    sections: list[dict[str, Any]], pack: Any, nodes: list[dict[str, Any]] | None = None
) -> list[tuple[str, str]]:
    """Reorder every section's keys in place; return (code, detail) warnings.

    A document leads a section only when it is primary and about the section
    (its nodes' own terms or the section's wording in title/abstract); a
    readable PDF on another subject is not promoted for having a file."""
    nodes = nodes or []
    warnings: list[tuple[str, str]] = []
    primaries = [p for p in pack.sources if is_primary(p, pack, nodes)]
    for section in sections:
        if is_frame(section):
            continue
        keys = list(section.get("evidence_keys") or [])
        packed = {k: pack.by_key(k) for k in keys}
        lead = [
            k
            for k in keys
            if packed[k] is not None
            and is_primary(packed[k], pack, nodes)
            and (
                is_legal_source(packed[k].source)
                or about_section(section, nodes, packed[k].source)
            )
        ]
        # In law the act or decision leads even when doctrine has full text.
        lead.sort(key=lambda k: not is_legal_source(packed[k].source))
        if not lead:
            wanted = set(section.get("scope_ids") or [])
            match = next((p for p in primaries if wanted & _scopes(p)), None)
            if match is not None:
                lead = [match.citation_key]
                packed[match.citation_key] = match
            else:
                warnings.append(
                    ("plan_material_gap", f"{section['title']}: без першоджерела")
                )
        section["evidence_keys"] = lead + [k for k in keys if k not in lead]
        if CASE_SECTION.search(section.get("title", "")) and not any(
            CASE_SOURCE.search(f"{p.source.title} {evidence_text(p.source) or ''}")
            for p in (packed.get(k) for k in section["evidence_keys"])
            if p is not None
        ):
            warnings.append(
                ("plan_material_gap", f"{section['title']}: у пакеті немає кейсів")
            )
    return warnings
