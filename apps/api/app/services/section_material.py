"""Material and task per section (recipe of 14.09, late evening).

Two rules the Compilatio scans supported four times: a subject section is
written from the two to four documents that answer its own question (windows
of their full text), not from a row of abstracts; the framing sections
(introduction, conclusions) are written last, as an answer to the research
question from the finished chapters, not as a description of the work.
"""

from __future__ import annotations

import re
from typing import Any

from app.services.source_evidence import evidence_text

MAX_SECTION_DOCUMENTS = 4
SENTENCE_END = re.compile(r"[.!?][»\")\]]?(?=\s|$)")
# Sixty thousand characters (~15k tokens) of finished chapters is the whole
# body of a bachelor's thesis; longer works are trimmed to head and tail of
# each chapter, where the argument and its result live.
CHAPTER_MATERIAL_CHARS = 60_000
_NUMBERING = (
    r"^\s*(?:(?:capitolo|chapter|розділ)\s+\S+\s*[.:-]?\s*)?(?:\d+(?:\.\d+)*[.)]?\s+)?"
)
FRAME_TITLES = re.compile(
    _NUMBERING + r"(?:introduzione|introduction|premessa|conclusioni|conclusion[s]?|"
    r"considerazioni\s+(?:finali|conclusive)|вступ|висновки)"
    r"(?:\s*$|\s+(?:generale|generali|finale|finali)\b|\s+(?:e|ed|and)\s+)",
    re.I,
)
FRAME_RULE = """This section frames the whole work; it is written LAST from chapter_material (the finished chapters) as an answer to the research question.
State the question and answer it with the chapters' concrete findings, evidence and limits, citing the same [KEY] markers and pages the chapters cite.
Do not describe the structure of the work, do not announce what each chapter does, do not summarise chapter by chapter, do not discuss the sources as a corpus.
"""


def is_frame(section: dict[str, Any]) -> bool:
    return bool(FRAME_TITLES.match(str(section.get("title") or "")))


def writing_order(outline: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Body sections in plan order, then the framing sections in plan order."""
    body = [s for s in outline if not is_frame(s)]
    return body + [s for s in outline if is_frame(s)]


def summaries(written: list[dict[str, Any]], chars: int) -> list[dict[str, str]]:
    return [{"title": s["title"], "summary": s["content"][-chars:]} for s in written]


def chapter_material(
    written: list[dict[str, Any]], cap: int = CHAPTER_MATERIAL_CHARS
) -> list[dict[str, str]]:
    """The finished sections' texts within the budget; head and tail of each
    when the whole does not fit."""
    rows = [
        (s["title"], str(s.get("content") or ""))
        for s in sorted(written, key=lambda s: s.get("section_index", 0))
    ]
    total = sum(len(text) for _, text in rows)
    if total <= cap:
        return [{"title": title, "text": text} for title, text in rows]
    out = []
    for title, text in rows:
        share = max(400, cap * len(text) // max(total, 1))
        if len(text) > share:
            head, tail = text[: share * 6 // 10], text[-(share * 4 // 10) :]
            text = head.rstrip() + " […] " + tail.lstrip()
        out.append({"title": title, "text": text})
    return out


def complete_prefix(text: str) -> str:
    """The text up to its last complete sentence."""
    ends = [m.end() for m in SENTENCE_END.finditer(text)]
    return text[: ends[-1]].strip() if ends else ""


def citable_keys(pack: Any, library: list[dict[str, Any]]) -> set[str]:
    """Pack sources with readable evidence plus the verified standard library."""
    verified = {r["key"] for r in library if r.get("verification_status") == "verified"}
    return {s.citation_key for s in pack.sources if evidence_text(s.source)} | verified
