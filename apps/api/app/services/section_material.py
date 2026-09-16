"""Material and task per section (recipes of 14.09 and 15.09).

A subject section is written from the few documents that answer its own
question (windows of their full text), primary sources first; the framing
sections are written last from a table of anchored findings, the
introduction posing the question and the conclusions answering it.
"""

from __future__ import annotations

import json
import re
from typing import Any

from app.services import writer_rules as rules
from app.services.source_evidence import evidence_text

MAX_SECTION_DOCUMENTS = 4
SENTENCE_END = re.compile(r"[.!?][»\")\]]?(?=\s|$)")
_NUMBERING = (
    r"^\s*(?:(?:capitolo|chapter|розділ)\s+\S+\s*[.:-]?\s*)?(?:\d+(?:\.\d+)*[.)]?\s+)?"
)
FRAME_TITLES = re.compile(
    _NUMBERING + r"(?:introduzione|introduction|premessa|conclusioni|conclusion[s]?|"
    r"considerazioni\s+(?:finali|conclusive)|вступ|висновки)"
    r"(?:\s*$|\s+(?:generale|generali|finale|finali)\b|\s+(?:e|ed|and)\s+)",
    re.I,
)
FRAME_RULE = rules.FRAME_RULE
# The detector marks the chapter walk in conclusions ("il primo capitolo...",
# 13-14 % in both files of 15-16.09) although the rule forbids it.
CHAPTER_WALK = re.compile(
    r"\b(?:il|nel|al|del)\s+(?:primo|secondo|terzo|quarto|quinto|sesto|ultimo)"
    r"\s+capitolo\b|\bsi\s+articola\b|\bnei\s+capitoli\s+(?:precedenti|successivi)\b"
    r"|\bthe\s+(?:first|second|third|fourth|fifth|last)\s+chapter\b",
    re.I,
)
FRAME_RETRY = """
REWRITE the whole section from scratch: the previous draft walked through the chapters ("il primo capitolo...", "si articola"), which is forbidden. Organise the findings by the logic of the answer to the research question; never name, number or sequence the chapters.
"""
MAX_ACADEMIC_DOCUMENTS = 2
# A statute, judgment or authority act contributes at most this many windows:
# 16.09.2026: the cap of three windows per legal document (15.09) halved the
# material per section (12 windows against 23 in rules2-B) and the body rose
# from 8 to 16-18 % AI while similarity stayed at 15-17 %; the character
# budgets alone bound a document again.
MAX_LEGAL_WINDOWS = 999
ANCHORED = re.compile(r"\[[\w:./-]+\]\s*,?\s*(?:pp?\.|art\.)\s*\d|\d")


def is_frame(section: dict[str, Any]) -> bool:
    return bool(FRAME_TITLES.match(str(section.get("title") or "")))


def writing_order(outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Body sections in plan order, then the framing sections last-to-first:
    the conclusions before the introduction, so the introduction is written
    from the conclusions' own anchors."""
    body = [s for s in outline if not is_frame(s)]
    return body + [s for s in reversed(outline) if is_frame(s)]


def summaries(written: list[dict[str, Any]], chars: int) -> list[dict[str, str]]:
    return [{"title": s["title"], "summary": s["content"][-chars:]} for s in written]


def frame_violations(text: str) -> list[str]:
    """Chapter-walk phrases a framing section must not contain."""
    return [m.group(0) for m in CHAPTER_WALK.finditer(text)]


def frame_rule(section: dict[str, Any]) -> str:
    title = str(section.get("title") or "")
    intro = re.match(
        _NUMBERING + r"(?:introduzione|introduction|premessa|вступ)", title, re.I
    )
    return rules.INTRO_RULE if intro else rules.CONCLUSIONS_RULE


def findings(
    written: list[dict[str, Any]], per_section: int = 3, cap: int = 12_000
) -> list[dict[str, Any]]:
    """Anchored facts of the finished sections, in plan order: the material
    of the framing sections instead of whole chapters."""
    rows = []
    used = 0
    for s in sorted(written, key=lambda s: s.get("section_index", 0)):
        sentences = re.split(
            r"(?<=[.!?])\s+(?=[A-ZÀ-Ý«(\[])", str(s.get("content") or "")
        )
        facts = [t.strip() for t in sentences if ANCHORED.search(t)][:per_section]
        row = {
            "title": s["title"],
            "question": s.get("question"),
            "facts": [f[:400] for f in facts],
            "conclusion": s.get("conclusion"),
        }
        used += len(json.dumps(row, ensure_ascii=False))
        if used > cap:
            break
        rows.append(row)
    return rows


def commentary_budget(outline: list[dict[str, Any]]) -> dict[str, Any]:
    """Shared across the sections of one work: how often an academic
    document may carry windows (a third of the sections) and the counts."""
    return {"cap": max(1, -(-len(outline) // 3)), "used": {}}


def complete_prefix(text: str) -> str:
    """The text up to its last complete sentence."""
    ends = [m.end() for m in SENTENCE_END.finditer(text)]
    return text[: ends[-1]].strip() if ends else ""


def citable_keys(pack: Any, library: list[dict[str, Any]]) -> set[str]:
    """Pack sources with readable evidence plus the verified standard library."""
    verified = {r["key"] for r in library if r.get("verification_status") == "verified"}
    return {s.citation_key for s in pack.sources if evidence_text(s.source)} | verified
