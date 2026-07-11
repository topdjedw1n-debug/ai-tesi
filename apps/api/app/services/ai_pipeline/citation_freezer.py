"""
Citation freezing for humanization.

The humanizer used to only *ask* the model to keep citation markers, then
check afterwards that ≥80% survived and roll the whole rewrite back if they
didn't (humanizer.py). Cheap models routinely failed that check (Phase 3
CIT_LOST). Freezing replaces the evidence base with short, inert placeholders
BEFORE the model sees the text, so there is nothing for it to reword; the
originals are substituted back verbatim afterwards. A missing placeholder is a
hard failure for that attempt — not a silent "80% is good enough".

Frozen spans:
- in-text citation markers [Author, Year] (same regex as CitationFormatter);
- direct quotations in quotation marks longer than ~10 words (the connective
  author prose is what the detector scores — a long verbatim quote is not ours
  to reword, and Turnitin excludes quoted-and-referenced text from scoring).
"""

import re

# Sentinel placeholders. The corner brackets ⟦⟧ never occur in academic prose
# and survive paraphrasing as opaque tokens; the model treats them as noise to
# copy through rather than text to reword.
_CITE_PLACEHOLDER = "⟦C{n}⟧"
_QUOTE_PLACEHOLDER = "⟦Q{n}⟧"

# [Author, Year] / [Author et al., Year] — identical to
# CitationFormatter.extract_citations_from_text so freezing and the citation
# formatter always agree on what a marker is.
_CITATION_RE = re.compile(r"[\[(][^\]\)]+,\s*\d{4}[a-z]?[\])]")

# Direct quotations. Straight ("), curly (“ ”) and guillemet (« ») pairs; the
# body is non-greedy and must not contain the opening delimiter again.
_QUOTE_RE = re.compile(
    r"“[^“”]+”"  # curly double
    r"|«[^«»]+»"  # guillemets (common in IT/UK/FR academic text)
    r'|"[^"]+"',  # straight double
)

# A quoted span shorter than this many words is likely a scare-quoted term or
# a title, not a block quotation — leave it in the prose so the humanizer can
# still smooth the sentence around it.
_MIN_QUOTE_WORDS = 10


class CitationFreezer:
    """Replace citations and long quotations with inert placeholders."""

    @staticmethod
    def freeze(text: str) -> tuple[str, dict[str, str]]:
        """
        Replace protected spans with placeholders.

        Returns (frozen_text, mapping) where mapping is placeholder -> original.
        Restore with :meth:`restore`; verify with :meth:`all_present`.
        """
        mapping: dict[str, str] = {}
        counter = {"c": 0, "q": 0}

        def _sub_citation(match: re.Match[str]) -> str:
            counter["c"] += 1
            key = _CITE_PLACEHOLDER.format(n=counter["c"])
            mapping[key] = match.group(0)
            return key

        def _sub_quote(match: re.Match[str]) -> str:
            span = match.group(0)
            # Count words inside the delimiters only.
            if len(span[1:-1].split()) < _MIN_QUOTE_WORDS:
                return span  # too short to be a block quote — leave in place
            counter["q"] += 1
            key = _QUOTE_PLACEHOLDER.format(n=counter["q"])
            mapping[key] = span
            return key

        # Freeze long quotations first so a [Author, Year] marker sitting
        # inside a quote is preserved as part of that quote, not double-frozen.
        frozen = _QUOTE_RE.sub(_sub_quote, text)
        # Grounded sections carry canonical [Key] markers through every
        # humanizer pass and render them only afterwards.  Freeze each marker
        # with a unique placeholder, preserving identity even when two MLA
        # citations would later render to the same author string.
        from app.services.ai_pipeline.citation_keys import internal_marker_spans

        chunks: list[str] = []
        cursor = 0
        for start, end, original in internal_marker_spans(frozen):
            chunks.append(frozen[cursor:start])
            counter["c"] += 1
            key = _CITE_PLACEHOLDER.format(n=counter["c"])
            mapping[key] = original
            chunks.append(key)
            cursor = end
        if chunks:
            chunks.append(frozen[cursor:])
            frozen = "".join(chunks)
        frozen = _CITATION_RE.sub(_sub_citation, frozen)
        return frozen, mapping

    @staticmethod
    def restore(text: str, mapping: dict[str, str]) -> str:
        """Substitute every placeholder back to its original span."""
        for key, original in mapping.items():
            text = text.replace(key, original)
        return text

    @staticmethod
    def all_present(text: str, mapping: dict[str, str]) -> bool:
        """True only if every frozen placeholder survived in ``text``."""
        return all(key in text for key in mapping)
