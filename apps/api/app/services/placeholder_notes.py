"""Editorial placeholders the writer may leave in a section, found by context.

A verification note about the material ("manuali e linee guida da verificare",
"materia manualistica soggetta a verifica": eleven real notes in the recorded
work of 09.09.2026), a note standing alone between punctuation or in brackets
("Da verificare.", "[da verificare]"), "[citation needed]" and a bare TODO are
placeholders. Ordinary Italian is not: "da verificare caso per caso" and
"resta, tuttavia, da verificare, poiché…" were reported as placeholders in the
law runs of 16.09.2026 and are prose.
"""

from __future__ import annotations

import re
from collections.abc import Iterable

MATERIAL = (
    r"\b(?:materia|manual[ei]|manualistica|linee\s+guida|font[ei]|dati|"
    r"riferiment[oi]|citazion[ei]|bibliografia|letteratura|test[oi]|"
    r"document[oi]|standard)"
)
VERIFICATION = re.compile(r"da\s+verificare|soggett[aeio]\s+a\s+verifica", re.I)


def placeholder_pattern(phrases: Iterable[str]) -> re.Pattern[str]:
    notes, exact = [], []
    for phrase in phrases:
        escaped = re.escape(phrase).replace(r"\ ", r"\s+")
        (notes if VERIFICATION.fullmatch(phrase) else exact).append(escaped)
    alternatives = [r"(?<!\w)(" + p + r")(?!\w)" for p in exact]
    if notes:
        note = "(?:" + "|".join(notes) + ")"
        alternatives += [
            MATERIAL + r"(?:\s+\w+){0,2}?[\s,:;]+(" + note + r")(?!\w)",
            r"(?:^|[.!?:;\n(\[])\s*(" + note + r")\s*(?:[.!?;)\]]|$)",
        ]
    return re.compile("|".join(alternatives), re.I | re.M)


def find_placeholders(text: str, phrases: Iterable[str]) -> list[str]:
    """Distinct placeholders in the text, lower-cased and sorted."""
    return sorted(
        {
            next(g for g in m.groups() if g).casefold()
            for m in placeholder_pattern(phrases).finditer(text)
        }
    )
