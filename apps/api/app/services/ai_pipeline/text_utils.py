"""
Shared text helpers for the source-grounding pipeline.

Pure, dependency-free utilities used by source_pack.py (topic scoring),
grounding_gate.py, and quality_metrics.py so tokenization / stop-word handling
stays consistent across them.
"""

from __future__ import annotations

import re
import unicodedata

# Multilingual stop words (EN + IT — the two languages that dominate current
# generation). Kept deliberately small: only high-frequency function words that
# add noise to topic-overlap scoring.
STOP_WORDS: frozenset[str] = frozenset(
    {
        # English
        "the",
        "a",
        "an",
        "and",
        "or",
        "of",
        "in",
        "on",
        "at",
        "to",
        "for",
        "with",
        "by",
        "from",
        "as",
        "is",
        "are",
        "be",
        "this",
        "that",
        "these",
        "those",
        "it",
        "its",
        "into",
        "about",
        "over",
        "between",
        "their",
        "there",
        "which",
        "who",
        "whom",
        "what",
        "how",
        "why",
        "not",
        "but",
        # Italian
        "il",
        "lo",
        "la",
        "i",
        "gli",
        "le",
        "un",
        "uno",
        "una",
        "di",
        "del",
        "della",
        "dei",
        "delle",
        "degli",
        "dal",
        "dalla",
        "e",
        "ed",
        "o",
        "od",
        "che",
        "chi",
        "con",
        "per",
        "tra",
        "fra",
        "su",
        "sul",
        "sulla",
        "nel",
        "nella",
        "nei",
        "nelle",
        "come",
        "non",
        "ma",
        "si",
        "sono",
        "essere",
        "questo",
        "questa",
        "questi",
        "queste",
        "suo",
        "sua",
        "loro",
        "anche",
        # Elided Italian articles/prepositions: the tokenizer splits
        # "dell'intelligenza" into "dell" + "intelligenza" — the stub carries
        # no content and dilutes topic-coverage scoring.
        "dell",
        "sull",
        "nell",
        "all",
        "dall",
        "quest",
        "senz",
    }
)


def ascii_fold(text: str) -> str:
    """Fold accented characters to ASCII (e.g. 'Pérez' -> 'Perez')."""
    if not text:
        return ""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def tokenize(text: str | None) -> list[str]:
    """Lowercase, unicode-aware word tokens (length >= 2), order preserved."""
    if not text:
        return []
    # \w is unicode-aware under Python 3 re; keep letters/digits, split the rest.
    return [
        t for t in re.findall(r"\w+", text.lower(), flags=re.UNICODE) if len(t) >= 2
    ]


def content_tokens(text: str | None) -> set[str]:
    """Distinct content tokens (stop words and pure-digit tokens removed)."""
    return {
        t
        for t in tokenize(text)
        if t not in STOP_WORDS and not t.isdigit() and len(t) > 2
    }


# Bracketed in-text citations ("[Rossi2021, 2021]") and per-line leading
# enumeration ("1. Introduzione") — digits that must NOT count as evidence.
_CITATION_RE = re.compile(r"\[[^\]]*\]")
_ENUMERATION_RE = re.compile(r"^\s*\d+[.)]\s", flags=re.MULTILINE)

# "Named system" evidence (Stage B4): a concrete named technology / platform /
# case counts as evidence even without numbers. Three deliberately narrow
# patterns to avoid matching ordinary sentence-initial capitalization:
# 1) Acronyms: 3-5 uppercase letters, optionally with digits ("SAP", "ERP",
#    "HANA", "GPT" in "GPT-4"). Deliberately NOT 2 letters: "AI"/"IT" appear
#    in every section of an AI thesis and would make the gate toothless.
#    Post-filtered below: Roman numerals ("XXI", "III"), long ALL-CAPS words
#    (headings like "INTRODUZIONE") and domain-ubiquitous acronyms don't count.
_ACRONYM_RE = re.compile(r"\b[A-Z]{3,}\d*\b")
# Roman-numeral-only tokens: "Nel XXI secolo", "Capitolo III" are filler, not
# named systems.
_ROMAN_ONLY_RE = re.compile(r"^[IVXLCDM]+$")
# Acronyms so common in AI/education theses that they carry no case evidence.
_GENERIC_ACRONYMS = frozenset(
    {"LLM", "LLMS", "NLP", "ICT", "TIC", "API", "GPU", "CPU", "PDF", "URL", "WWW"}
)
# 2) CamelCase tokens ("ChatGPT", "DeepMind", "TensorFlow") — an uppercase
#    letter appearing after a lowercase letter inside one word. Min length 5
#    (filtered below) so unit-style tokens ("PhD", "kWh") don't count.
_CAMELCASE_RE = re.compile(r"\b[A-Za-z]*[a-z][A-Z][A-Za-z]*\b")
# 3) Mid-sentence capitalized bigram ("Industria 4.0" is caught by numbers;
#    "Amazon Web Services" needs this): two adjacent capitalized words
#    genuinely inside a sentence — the preceding character must be a
#    lowercase letter/digit/comma, which excludes sentence starts, headings
#    and line starts. Same-line only ([ \t], not \s) so a heading followed by
#    a capitalized sentence start can't bridge the newline.
#    (à-öø-ÿ = Latin-1 letters without the ÷ sign.)
_MIDSENTENCE_PROPER_BIGRAM_RE = re.compile(
    r"(?<=[a-zà-öø-ÿ0-9,;:)])[ \t][A-Z][a-zà-öø-ÿ]+[ \t]+[A-Z][a-zà-öø-ÿ]+\b"
)
# Narrative-citation / attribution verbs (IT + EN): a capitalized bigram right
# after one of these is an AUTHOR name ("come sostiene Mario Rossi"), not a
# named system. Checked against the ~3 words before the bigram.
_ATTRIBUTION_TAIL_RE = re.compile(
    r"(?:\b(?:sostiene|sostengono|afferma|affermano|osserva|osservano|scrive|"
    r"scrivono|nota|notano|suggerisce|suggeriscono|evidenzia|evidenziano|"
    r"secondo|according\s+to|argues?|claims?|states?|notes?|suggests?)\b"
    r"[^.;:!?]{0,20})$",
    flags=re.IGNORECASE,
)


def _acronym_evidence(cleaned: str) -> bool:
    for match in _ACRONYM_RE.finditer(cleaned):
        token = match.group(0)
        letters = token.rstrip("0123456789")
        if _ROMAN_ONLY_RE.match(letters):
            continue  # "XXI", "III" — Roman numerals, not systems
        if len(letters) > 5:
            continue  # "INTRODUZIONE" — an ALL-CAPS heading, not an acronym
        if letters in _GENERIC_ACRONYMS:
            continue
        return True
    return False


def _camelcase_evidence(cleaned: str) -> bool:
    return any(len(match.group(0)) >= 5 for match in _CAMELCASE_RE.finditer(cleaned))


def _bigram_evidence(cleaned: str) -> bool:
    for match in _MIDSENTENCE_PROPER_BIGRAM_RE.finditer(cleaned):
        if _ATTRIBUTION_TAIL_RE.search(cleaned[: match.start() + 1]):
            continue  # "come sostiene Mario Rossi" — an author, not a system
        return True
    return False


def contains_named_system(text: str | None) -> bool:
    """True if the text names a concrete system/technology/case.

    Heuristics: acronyms (SAP, ERP — but not Roman numerals, ALL-CAPS
    headings or ubiquitous LLM/NLP-style abbreviations), CamelCase product
    names (ChatGPT, TensorFlow — min length 5, so not PhD/kWh), or a
    capitalized bigram in the middle of a sentence (Amazon Web Services —
    unless it follows an attribution verb and is therefore an author name).
    Bracketed citations are stripped first so author names in
    "[Rossi2021, 2021]" can't trigger it.
    """
    if not text:
        return False
    cleaned = _CITATION_RE.sub(" ", text)
    cleaned = _ENUMERATION_RE.sub(" ", cleaned)
    return (
        _acronym_evidence(cleaned)
        or _camelcase_evidence(cleaned)
        or _bigram_evidence(cleaned)
    )


def contains_concrete_evidence(text: str | None) -> bool:
    """True if the text carries a concrete detail: a numeric fact OR a named
    system/case (Stage B4 — sources often support qualitative case evidence
    without numbers; requiring digits produced false evidence-gate failures).

    Numbers: percentages ("30%"), decimals ("2,5" / "3.7") and multi-digit
    numbers ("1200") — AFTER stripping bracketed citations and per-line
    section enumeration, which is what fooled the previous naive `\\d` check
    (citation years and "1." headings are not evidence).

    Known limitation: a bare year in prose ("nel 2023") still counts — it is a
    concrete, checkable fact, and excluding years would also drop real data
    like "nel 2023 il 40% ...". Shared by quality_metrics.evidence_presence
    and grounding_gate.evaluate_grounding — keep them consistent.
    """
    if not text:
        return False
    cleaned = _CITATION_RE.sub(" ", text)
    cleaned = _ENUMERATION_RE.sub(" ", cleaned)
    return bool(
        re.search(r"\d+\s*%", cleaned)
        or re.search(r"\b\d+[.,]\d+\b", cleaned)
        or re.search(r"\b\d{2,}\b", cleaned)
        or contains_named_system(text)
    )
