"""
Stylometric human-likeness measurer.

Free, offline, dependency-free proxy for the CONFIRMED human-vs-AI markers from
the 03.07.2026 detection research (docs/phase1-runs/HUMANIZATION-RESEARCH.md,
"Маркери AI-тексту" section). It lets us measure a draft BEFORE and AFTER
humanization without spending a detector API call, so the humanization prompt
can be tuned against the markers offline instead of only through paid runs.

IMPORTANT — this is NOT an AI detector and does NOT predict GPTZero/Compilatio.
Those are trained neural classifiers; this only quantifies the specific
linguistic features that peer-reviewed work found to separate human from AI
academic prose. A rewrite that moves these markers in the human direction is
*more likely* to read as human, but the real submission gate stays Compilatio.

Markers computed — every one CONFIRMED (3-0) in the research. The refuted
"folk" markers (lexical diversity / type-token ratio, and adding
typos/imperfections) are DELIBERATELY absent: the research killed them 0-3, so
optimizing toward them would be noise at best.

  burstiness      variation in sentence length. Human prose is uneven — some
                  very short sentences, some very long; AI clusters in a narrow
                  10-30 word band. Higher variation = more human.
  nominalization  density of abstract -tion/-ment/-zione/-mento nouns. AI
                  writes noun-heavy ("the analysis was conducted"); humans use
                  more verbs ("we analyzed"). Lower density = more human.
  pronoun_ratio   personal/demonstrative pronouns per word. AI uses fewer.
  auxiliary_ratio auxiliary/modal verbs per word. AI uses fewer.
  readability     mean sentence + word length proxy. AI reads harder (lower
                  Flesch). More readable = more human.

Note on passive voice: the research found AI uses ~3x LESS passive than humans,
so passive density is intentionally NOT scored as an AI marker — reducing it
would push the wrong way.

Language-aware for English and Italian (the two languages that dominate
current generation). Other languages fall back to the English lexicons for the
function-word ratios; burstiness and readability are language-agnostic.

All thresholds below are DIRECTIONAL heuristics, not calibrated cut-offs, and
the empirical work behind them is English-only — treat the composite as a
relative before/after signal, never as an absolute verdict.
"""

from __future__ import annotations

import re
from statistics import mean, pstdev

# --- Sentence / word segmentation ------------------------------------------
# Sentence boundary: terminal punctuation followed by whitespace/end, OR a
# blank line. Deliberately simple — good enough for length statistics; it does
# not need to be linguistically perfect.
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?…])\s+|\n{2,}")
_WORD_RE = re.compile(r"[A-Za-zÀ-ÖØ-öø-ÿĀ-ž]+", flags=re.UNICODE)
# Citation markers / frozen placeholders must not distort word or length
# counts, so strip them before measuring.
_STRIP_RE = re.compile(r"\[[^\]]*\]|⟦[^⟧]*⟧")


# --- Function-word lexicons (proxies, not exhaustive POS tagging) ----------
_PRONOUNS_EN = frozenset(
    {
        "i",
        "we",
        "you",
        "he",
        "she",
        "it",
        "they",
        "me",
        "us",
        "him",
        "her",
        "them",
        "my",
        "our",
        "your",
        "his",
        "its",
        "their",
        "mine",
        "ours",
        "yours",
        "hers",
        "theirs",
        "this",
        "that",
        "these",
        "those",
        "one",
        "oneself",
        "ourselves",
        "myself",
        "themselves",
        "who",
        "whom",
        "whose",
    }
)
_PRONOUNS_IT = frozenset(
    {
        "io",
        "noi",
        "tu",
        "voi",
        "lui",
        "lei",
        "loro",
        "egli",
        "ella",
        "esso",
        "essa",
        "essi",
        "esse",
        "mi",
        "ti",
        "ci",
        "vi",
        "si",
        "me",
        "te",
        "se",
        "gli",
        "le",
        "lo",
        "la",
        "ne",
        "questo",
        "questa",
        "questi",
        "queste",
        "quello",
        "quella",
        "quelli",
        "quelle",
        "ciò",
        "costui",
        "colui",
        "coloro",
        "mio",
        "mia",
        "miei",
        "mie",
        "nostro",
        "nostra",
        "nostri",
        "nostre",
        "suo",
        "sua",
        "suoi",
        "sue",
        "chi",
        "cui",
    }
)
_AUXILIARIES_EN = frozenset(
    {
        "be",
        "am",
        "is",
        "are",
        "was",
        "were",
        "been",
        "being",
        "have",
        "has",
        "had",
        "having",
        "do",
        "does",
        "did",
        "doing",
        "will",
        "would",
        "shall",
        "should",
        "can",
        "could",
        "may",
        "might",
        "must",
        "ought",
    }
)
_AUXILIARIES_IT = frozenset(
    {
        # essere
        "sono",
        "sei",
        "è",
        "siamo",
        "siete",
        "era",
        "eri",
        "eravamo",
        "eravate",
        "erano",
        "fu",
        "furono",
        "sarà",
        "saranno",
        "sarebbe",
        "sarebbero",
        "stato",
        "stata",
        "stati",
        "state",
        "essere",
        "sia",
        "siano",
        "fosse",
        "fossero",
        # avere
        "ho",
        "hai",
        "ha",
        "abbiamo",
        "avete",
        "hanno",
        "avevo",
        "avevi",
        "aveva",
        "avevamo",
        "avevano",
        "avrà",
        "avrebbe",
        "avrebbero",
        "avuto",
        "avere",
        "abbia",
        "abbiano",
        "avesse",
        # modali
        "posso",
        "puoi",
        "può",
        "possiamo",
        "potete",
        "possono",
        "potrebbe",
        "potrebbero",
        "potere",
        "devo",
        "devi",
        "deve",
        "dobbiamo",
        "dovete",
        "devono",
        "dovrebbe",
        "dovrebbero",
        "dovere",
        "voglio",
        "vuoi",
        "vuole",
        "vogliamo",
        "volete",
        "vogliono",
        "volere",
    }
)

# Nominalization suffixes (abstract deverbal/deadjectival nouns). Applied only
# to tokens long enough that the suffix is not the whole word.
_NOMINAL_SUFFIXES_EN = (
    "tion",
    "sion",
    "ment",
    "ness",
    "ity",
    "ance",
    "ence",
    "ism",
    "ized",
    "isation",
    "ization",
)
_NOMINAL_SUFFIXES_IT = (
    "zione",
    "sione",
    "mento",
    "ità",
    "anza",
    "enza",
    "ismo",
    "aggio",
    "azione",
)


def _clamp01(value: float) -> float:
    return 0.0 if value < 0.0 else 1.0 if value > 1.0 else value


def _lexicons(language: str) -> tuple[frozenset[str], frozenset[str], tuple[str, ...]]:
    """Pronoun set, auxiliary set and nominalization suffixes for a language.

    Italian gets its own lexicons; every other language (including English)
    uses the English function-word sets plus the union of EN+IT suffixes so an
    unexpected language still yields a usable relative signal.
    """
    if language == "it":
        return _PRONOUNS_IT, _AUXILIARIES_IT, _NOMINAL_SUFFIXES_IT
    return _PRONOUNS_EN, _AUXILIARIES_EN, _NOMINAL_SUFFIXES_EN + _NOMINAL_SUFFIXES_IT


def _sentences(text: str) -> list[str]:
    return [s for s in (p.strip() for p in _SENTENCE_SPLIT_RE.split(text)) if s]


def human_likeness(text: str, language: str = "en") -> dict[str, float | int | None]:
    """Measure the confirmed human-vs-AI markers on ``text``.

    Returns a flat dict of raw metrics, per-marker sub-scores in [0, 1] (1 =
    most human-like), and a composite ``human_likeness`` in [0, 100]. Fields
    are None when the text is too short to measure a given marker (fewer than a
    handful of sentences / words); the composite then weights only what could
    be measured. Pure and side-effect free — safe to call on every draft.
    """
    pronouns, auxiliaries, nominal_suffixes = _lexicons(language)

    cleaned = _STRIP_RE.sub(" ", text or "")
    sentences = _sentences(cleaned)
    sent_lengths = [len(_WORD_RE.findall(s)) for s in sentences]
    sent_lengths = [n for n in sent_lengths if n > 0]
    words = [w.lower() for w in _WORD_RE.findall(cleaned)]
    total_words = len(words)

    # --- burstiness: coefficient of variation of sentence lengths ----------
    burstiness_cv: float | None = None
    ai_band_share: float | None = None
    burstiness_score: float | None = None
    if len(sent_lengths) >= 4:
        avg_len = mean(sent_lengths)
        if avg_len > 0:
            burstiness_cv = pstdev(sent_lengths) / avg_len
            # 0.30 CV reads as flat/AI, 0.70+ as human-uneven.
            burstiness_score = _clamp01((burstiness_cv - 0.30) / (0.70 - 0.30))
        ai_band_share = sum(1 for n in sent_lengths if 10 <= n <= 30) / len(
            sent_lengths
        )

    # --- function-word and nominalization densities ------------------------
    nominalization_density: float | None = None
    pronoun_ratio: float | None = None
    auxiliary_ratio: float | None = None
    nominalization_score: float | None = None
    pronoun_score: float | None = None
    auxiliary_score: float | None = None
    if total_words >= 40:
        nominal_count = sum(
            1 for w in words if len(w) >= 6 and w.endswith(nominal_suffixes)
        )
        nominalization_density = nominal_count / total_words
        # 0.02 density is verb-driven/human, 0.08 is noun-heavy/AI.
        nominalization_score = _clamp01((0.08 - nominalization_density) / (0.08 - 0.02))

        pronoun_ratio = sum(1 for w in words if w in pronouns) / total_words
        pronoun_score = _clamp01((pronoun_ratio - 0.02) / (0.09 - 0.02))

        auxiliary_ratio = sum(1 for w in words if w in auxiliaries) / total_words
        auxiliary_score = _clamp01((auxiliary_ratio - 0.02) / (0.07 - 0.02))

    # --- readability proxy: average sentence + word length -----------------
    avg_sentence_len: float | None = None
    avg_word_len: float | None = None
    readability_score: float | None = None
    if sent_lengths and total_words >= 40:
        avg_sentence_len = mean(sent_lengths)
        avg_word_len = mean(len(w) for w in words)
        # Harder text = longer sentences and longer words = more AI-like.
        hardness = 0.6 * _clamp01((avg_sentence_len - 12) / (30 - 12)) + 0.4 * _clamp01(
            (avg_word_len - 4.5) / (6.5 - 4.5)
        )
        readability_score = 1.0 - hardness

    # --- composite (weighted mean of whatever could be measured) -----------
    weighted = [
        (burstiness_score, 0.30),
        (nominalization_score, 0.25),
        (pronoun_score, 0.20),
        (auxiliary_score, 0.15),
        (readability_score, 0.10),
    ]
    present = [(s, w) for s, w in weighted if s is not None]
    composite: float | None
    if present:
        total_w = sum(w for _, w in present)
        composite = round(100 * sum(s * w for s, w in present) / total_w, 1)
    else:
        composite = None

    return {
        "human_likeness": composite,
        "burstiness_cv": round(burstiness_cv, 3) if burstiness_cv is not None else None,
        "ai_band_share": round(ai_band_share, 3) if ai_band_share is not None else None,
        "nominalization_density": round(nominalization_density, 4)
        if nominalization_density is not None
        else None,
        "pronoun_ratio": round(pronoun_ratio, 4) if pronoun_ratio is not None else None,
        "auxiliary_ratio": round(auxiliary_ratio, 4)
        if auxiliary_ratio is not None
        else None,
        "avg_sentence_len": round(avg_sentence_len, 1)
        if avg_sentence_len is not None
        else None,
        "avg_word_len": round(avg_word_len, 2) if avg_word_len is not None else None,
        "sentence_count": len(sent_lengths),
        "word_count": total_words,
        "burstiness_score": round(burstiness_score, 3)
        if burstiness_score is not None
        else None,
        "nominalization_score": round(nominalization_score, 3)
        if nominalization_score is not None
        else None,
        "pronoun_score": round(pronoun_score, 3) if pronoun_score is not None else None,
        "auxiliary_score": round(auxiliary_score, 3)
        if auxiliary_score is not None
        else None,
        "readability_score": round(readability_score, 3)
        if readability_score is not None
        else None,
    }
