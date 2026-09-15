"""Which sources are law (statutes, judgments, acts): shared by the evidence
policy and the citation renderer without importing either."""

from __future__ import annotations

import re
from typing import Any

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
STATUTE_TITLES = re.compile(
    r"^\s*(?:Legge|L\.|Decreto|D\.\s?Lgs\.?|D\.\s?L\.|D\.P\.R\.|Regolamento|"
    r"Direttiva|Regulation|Directive|Statuto|Codice)",
    re.I,
)


def is_legal_source(source: Any) -> bool:
    authors = " ".join(getattr(source, "authors", None) or [])
    title = str(getattr(source, "title", "") or "")
    return bool(LEGAL_AUTHORS.search(authors)) or bool(LEGAL_TITLES.match(title))


def is_statute(source: Any) -> bool:
    return bool(STATUTE_TITLES.match(str(getattr(source, "title", "") or "")))
