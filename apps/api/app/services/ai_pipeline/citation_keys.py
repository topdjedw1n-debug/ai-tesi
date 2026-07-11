"""Resolve model-written source-pack markers without losing citations.

The writer is instructed to cite the exact ``[Key]`` values from a
``SourcePack``.  In practice models occasionally restore diacritics or rebuild
the key from the first author's surname.  This module maps only deterministic,
unique variants back to the canonical pack key.  Unknown or ambiguous markers
are deliberately left untouched so the quality gate can block them; they are
never silently deleted.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Any

from app.services.ai_pipeline.citation_formatter import CitationFormatter, CitationStyle

_BRACKET_RE = re.compile(r"\[([^\[\]\n]{1,160})\]")
_KEY_PART_RE = re.compile(
    r"^\s*(?P<key>[^\s,;|\[\]\(\)]+?(?:\d{1,4}|nd)[a-z]*)"
    r"(?P<locator>"
    r"\s*(?:,|\||:)\s*"
    r"(?:(?:p|pp|page|pages|ch|chap|chapter|chapters|sec|section|sections|§|§§)\.?\s*)?"
    r"(?:\d+(?:\.\d+)*(?:\s*[-–—]\s*\d+(?:\.\d+)*)?"
    r"|[ivxlcdm]+(?:\s*[-–—]\s*[ivxlcdm]+)?)"
    r")?\s*$",
    re.IGNORECASE,
)
_YEAR_SUFFIX_RE = re.compile(r"\d{1,4}([a-z]+)$", re.IGNORECASE)
_NON_CITATION_PREFIXES = {
    "appendix",
    "chapter",
    "eq",
    "equation",
    "fig",
    "figure",
    "iso",
    "page",
    "section",
    "tab",
    "table",
}

_LATIN_TRANSLITERATION = str.maketrans(
    {
        "ı": "i",
        "Ł": "L",
        "ł": "l",
        "Ø": "O",
        "ø": "o",
        "Đ": "D",
        "đ": "d",
        "Ð": "D",
        "ð": "d",
        "Þ": "Th",
        "þ": "th",
        "Æ": "Ae",
        "æ": "ae",
        "Œ": "Oe",
        "œ": "oe",
        "ß": "ss",
    }
)


def fold_citation_key(value: str | None) -> str:
    """Unicode/case/punctuation-insensitive key used only for matching."""
    if not value:
        return ""
    translated = str(value).translate(_LATIN_TRANSLITERATION)
    decomposed = unicodedata.normalize("NFKD", translated)
    without_marks = "".join(
        char for char in decomposed if not unicodedata.combining(char)
    )
    return "".join(char for char in without_marks.casefold() if char.isalnum())


def year_suffix_from_citation_key(value: str | None) -> str:
    """Return the complete collision suffix from an AuthorYYYY key."""
    match = _YEAR_SUFFIX_RE.search(str(value or ""))
    return match.group(1).lower() if match else ""


def internal_marker_keys(text: str | None) -> list[str]:
    """Return pack-like keys still present in square brackets."""
    keys: list[str] = []
    for match in _BRACKET_RE.finditer(text or ""):
        parsed = _parse_group(match.group(1))
        if parsed is not None:
            keys.extend(part.key for part in parsed)
    return keys


@dataclass(frozen=True)
class MarkerConversion:
    """Canonical marker view plus the user-facing rendered citation view."""

    content_with_markers: str
    content: str
    used_keys: list[str]
    unresolved_keys: list[str]


def convert_pack_markers(
    text: str,
    pack: Any,
    *,
    citation_style: Any,
) -> MarkerConversion:
    """Resolve and render every deterministic source-pack marker in ``text``.

    Resolution is deliberately exact after normalization.  Author-surname
    aliases are accepted only when they point to one pack source; collisions
    remain unresolved and therefore block the section later in the pipeline.
    """

    sources_by_key = {
        str(packed.citation_key): packed for packed in getattr(pack, "sources", [])
    }
    alias_index = _build_alias_index(list(sources_by_key.values()))
    mla_titles = _mla_disambiguation_titles(list(sources_by_key.values()))
    used: list[str] = []
    unresolved: list[str] = []

    def resolve(raw_key: str) -> str | None:
        candidates = alias_index.get(fold_citation_key(raw_key), set())
        return next(iter(candidates)) if len(candidates) == 1 else None

    def canonical_replacement(match: re.Match[str]) -> str:
        raw_keys = _parse_group(match.group(1))
        if raw_keys is None:
            return match.group(0)
        canonical: list[str] = []
        for part in raw_keys:
            resolved = resolve(part.key)
            if resolved is None:
                unresolved.append(part.key)
                canonical.append(part.render())
                continue
            canonical.append(part.render(key=resolved))
            if resolved not in used:
                used.append(resolved)
        return "[" + "; ".join(canonical) + "]"

    marker_view = _BRACKET_RE.sub(canonical_replacement, text or "")

    def rendered_replacement(match: re.Match[str]) -> str:
        raw_keys = _parse_group(match.group(1))
        if raw_keys is None:
            return match.group(0)
        resolved_parts: list[tuple[_MarkerPart, str]] = []
        for part in raw_keys:
            resolved = resolve(part.key)
            if resolved is None:
                return match.group(0)
            resolved_parts.append((part, resolved))

        formatted: list[str] = []
        for part, canonical_key in resolved_parts:
            packed = sources_by_key.get(canonical_key)
            source = getattr(packed, "source", None)
            authors = list(getattr(source, "authors", None) or [])
            year = getattr(source, "year", None)
            if not authors or not year:
                unresolved.append(canonical_key)
                return match.group(0)
            year_suffix = year_suffix_from_citation_key(canonical_key)
            formatted.append(
                _format_with_locator(
                    authors,
                    int(year),
                    citation_style=citation_style,
                    year_suffix=year_suffix,
                    locator=part.locator,
                    disambiguation_title=mla_titles.get(canonical_key),
                )
            )

        if len(formatted) == 1:
            rendered_value = formatted[0]
        else:
            # Every supported formatter returns a parenthetical citation.  Merge
            # multi-source groups into one pair of parentheses.
            inner = [
                value[1:-1] if value.startswith("(") and value.endswith(")") else value
                for value in formatted
            ]
            rendered_value = "(" + "; ".join(inner) + ")"
        return rendered_value

    rendered = _BRACKET_RE.sub(rendered_replacement, marker_view)
    return MarkerConversion(
        content_with_markers=marker_view,
        content=rendered,
        used_keys=used,
        unresolved_keys=list(dict.fromkeys(unresolved)),
    )


@dataclass(frozen=True)
class _MarkerPart:
    key: str
    locator: str = ""

    def render(self, *, key: str | None = None) -> str:
        return f"{key or self.key}{self.locator}"


def _parse_group(group: str) -> list[_MarkerPart] | None:
    """Parse one ``[Key; OtherKey]`` group, or return None for normal prose."""
    raw_parts = group.split(";")
    parsed: list[_MarkerPart] = []
    for raw_part in raw_parts:
        match = _KEY_PART_RE.fullmatch(raw_part)
        if match is None:
            return None
        key = match.group("key")
        if _looks_like_non_citation_label(key):
            return None
        parsed.append(_MarkerPart(key=key, locator=match.group("locator") or ""))
    return parsed or None


def internal_marker_spans(text: str | None) -> list[tuple[int, int, str]]:
    """Return exact spans for pack markers so the humanizer can freeze them."""
    spans: list[tuple[int, int, str]] = []
    for match in _BRACKET_RE.finditer(text or ""):
        if _parse_group(match.group(1)) is not None:
            spans.append((match.start(), match.end(), match.group(0)))
    return spans


def internal_marker_groups(text: str | None) -> list[tuple[str, list[str]]]:
    """Return each canonical marker and the source keys it contains."""
    groups: list[tuple[str, list[str]]] = []
    for match in _BRACKET_RE.finditer(text or ""):
        parsed = _parse_group(match.group(1))
        if parsed is not None:
            groups.append((match.group(0), [part.key for part in parsed]))
    return groups


def _looks_like_non_citation_label(key: str) -> bool:
    match = re.match(
        r"(?P<prefix>.*?)(?:\d{1,4}|nd)[a-z]*$",
        key,
        re.IGNORECASE,
    )
    if match is None:
        return True
    prefix = fold_citation_key(match.group("prefix"))
    return prefix in _NON_CITATION_PREFIXES


def _format_with_locator(
    authors: list[str],
    year: int,
    *,
    citation_style: Any,
    year_suffix: str,
    locator: str,
    disambiguation_title: str | None,
) -> str:
    if re.fullmatch(r"\s*,\s*\d{4}\s*", locator or ""):
        locator = ""
    locator_match = re.fullmatch(
        r"\s*(?:,|\||:)\s*"
        r"(?:(?P<label>p|pp|page|pages|ch|chap|chapter|chapters|sec|section|sections|§|§§)\.?\s*)?"
        r"(?P<value>\d+(?:\.\d+)*(?:\s*[-–—]\s*\d+(?:\.\d+)*)?"
        r"|[ivxlcdm]+(?:\s*[-–—]\s*[ivxlcdm]+)?)\s*",
        locator or "",
        re.IGNORECASE,
    )
    label = (locator_match.group("label") if locator_match else "") or ""
    value = (locator_match.group("value") if locator_match else "") or ""
    is_single_page = (
        bool(value)
        and re.fullmatch(r"\d+", value) is not None
        and label.casefold() in {"", "p", "page"}
    )
    if not locator or is_single_page:
        return CitationFormatter.format_intext(
            authors,
            year,
            style=citation_style,
            page=(int(value) if is_single_page else None),
            year_suffix=year_suffix,
            disambiguation_title=disambiguation_title,
        )

    rendered = CitationFormatter.format_intext(
        authors,
        year,
        style=citation_style,
        year_suffix=year_suffix,
        disambiguation_title=disambiguation_title,
    )
    if locator_match is None or not rendered.endswith(")"):
        return rendered
    label_folded = label.casefold()
    is_page = label_folded in {"", "p", "pp", "page", "pages"}
    if is_page:
        plural = label_folded in {"pp", "pages"} or bool(re.search(r"[-–—]", value))
        locator_text = f"{'pp.' if plural else 'p.'} {value}"
    elif label_folded in {"ch", "chap", "chapter", "chapters"}:
        locator_text = f"ch. {value}"
    else:
        locator_text = f"sec. {value}"
    style_value = str(getattr(citation_style, "value", citation_style)).casefold()
    if style_value == "mla":
        suffix = f" {value}" if is_page else f", {locator_text}"
    else:
        suffix = f", {locator_text}"
    return rendered[:-1] + suffix + ")"


def _mla_disambiguation_titles(packed_sources: list[Any]) -> dict[str, str]:
    """Return a unique shortened title for each ambiguous MLA author label."""
    groups: dict[str, list[Any]] = {}
    for packed in packed_sources:
        source = getattr(packed, "source", None)
        authors = list(getattr(source, "authors", None) or [])
        year = getattr(source, "year", None)
        if not authors or not year:
            continue
        author_label = CitationFormatter.format_intext(
            authors,
            int(year),
            style=CitationStyle.MLA,
        ).casefold()
        groups.setdefault(author_label, []).append(packed)

    titles: dict[str, str] = {}
    for items in groups.values():
        if len(items) < 2:
            continue
        word_lists = [
            re.findall(r"[^\W_]+(?:[-’'][^\W_]+)*", str(item.source.title or ""))
            for item in items
        ]
        for index, (item, words) in enumerate(zip(items, word_lists, strict=True)):
            if not words:
                continue
            chosen = " ".join(words)
            for width in range(1, len(words) + 1):
                candidate = " ".join(words[:width])
                other_prefixes = {
                    " ".join(other[:width]).casefold()
                    for other_index, other in enumerate(word_lists)
                    if other_index != index
                }
                if candidate.casefold() not in other_prefixes:
                    chosen = candidate
                    break
            titles[str(item.citation_key)] = chosen
    return titles


def _build_alias_index(packed_sources: list[Any]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for packed in packed_sources:
        canonical = str(getattr(packed, "citation_key", "") or "")
        if not canonical:
            continue
        aliases = {canonical}
        source = getattr(packed, "source", None)
        authors = list(getattr(source, "authors", None) or [])
        year = getattr(source, "year", None)
        suffix_match = _YEAR_SUFFIX_RE.search(canonical)
        suffix = suffix_match.group(1).lower() if suffix_match else ""
        if authors and year:
            surname = _author_surname(authors[0])
            surname_variants = {surname}
            surname_variants.update(
                part for part in re.split(r"[-\s]+", surname) if part
            )
            for variant in surname_variants:
                aliases.add(f"{variant}{int(year)}{suffix}")
                # Models often omit an APA a/b suffix.  This alias is safe
                # only when unique; the set-valued index enforces that.
                if suffix:
                    aliases.add(f"{variant}{int(year)}")
        for alias in aliases:
            folded = fold_citation_key(alias)
            if folded:
                index.setdefault(folded, set()).add(canonical)
    return index


def _author_surname(author: str) -> str:
    value = (author or "").strip()
    if not value:
        return ""
    return value.split(",", 1)[0].strip() if "," in value else value.split()[-1]
