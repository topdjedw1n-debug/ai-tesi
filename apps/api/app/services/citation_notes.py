"""Italian traditional citations: every pack marker becomes a footnote.

Order 24286128 (24.09.2026): the university's Vademecum asks for note a piè di
pagina instead of author-year parentheses. The first note on a work gives the
full reference (Nome Cognome, *Titolo*, in «Rivista», anno, p. N); a repeat of
the note just before is "Ibidem" or "Ibid., p. N"; a later repeat is
"Cognome, op. cit., p. N" ("Cognome, *Titolo breve*, cit." when the surname
names two cited works). A marker used as a noun ("lo studio di [KEY]") keeps
the authors' surnames in the sentence. Pure text: NOTE_MARK placeholders are
turned into Word footnotes by the DOCX exporter.
"""

from __future__ import annotations

import re
from html import unescape
from typing import Any

from app.services.citation_render import normalize_locators, sort_key

NOTE_MARK = re.compile("\ue000(\\d+)\ue001")
CITE = re.compile(
    r"\[(STD:[^\[\]\n]+|[\w:./-]+)\](?:\s*,?\s*(pp?)\.\s*(\d+(?:\s*[-–,]\s*\d+)*))?"
)
# Open-access repositories reported as the venue of theses and preprints:
# "in «eScholarship (California Digital Library)»" reads as a journal.
REPOSITORY = re.compile(
    r"repositor|eScholarship|Scholarship at|Open Research|DepositOnce|"
    r"Institutional|Archive|ScholarWorks|OpenstarTs|UvA-DARE|Academic Bibliography",
    re.I,
)
PARTICLES = {"de", "di", "da", "del", "della", "dei", "van", "von", "der", "den", "du"}
# The word before a marker that makes the marker a noun of the sentence.
NOUN_BEFORE = re.compile(
    r"(?:\b(?:di|del|della|dello|dei|degli|delle|a|ad|al|alla|allo|ai|agli|alle|"
    r"da|dal|dalla|dallo|dai|dagli|dalle|in|nel|nella|nello|nei|negli|nelle|"
    r"su|sul|sulla|sullo|sui|sugli|sulle|con|per|tra|fra|e|ed|come|che|"
    r"secondo|verso|presso)|^|[.!?:]|\n)\s*$",
    re.I,
)


def _note(number: int) -> str:
    return f"\ue000{number}\ue001"


def surname(name: str) -> str:
    name = " ".join(str(name).split())
    if "," in name:
        return name.split(",", 1)[0].strip()
    parts = name.split()
    i = len(parts) - 1
    while i > 0 and parts[i - 1].lower() in PARTICLES:
        i -= 1
    return " ".join(parts[i:])


def display_name(name: str) -> str:
    name = " ".join(str(name).split())
    if "," in name:
        family, given = (p.strip() for p in name.split(",", 1))
        return f"{given} {family}".strip()
    return name


def join_names(names: list[str]) -> str:
    if len(names) > 3:
        return f"{names[0]} et al."
    if len(names) == 1:
        return names[0]
    return ", ".join(names[:-1]) + " e " + names[-1]


def _authors(source: Any) -> list[str]:
    return [a for a in (getattr(source, "authors", None) or []) if str(a).strip()]


def _title(source: Any) -> str:
    title = re.sub(r"\s*\n\s*", ". ", unescape(str(source.title or "")).strip())
    return " ".join(title.split()).rstrip(" .")


TRAILING = {
    "di",
    "del",
    "della",
    "dei",
    "degli",
    "delle",
    "in",
    "nel",
    "negli",
    "nella",
}
TRAILING |= {
    "e",
    "a",
    "da",
    "per",
    "con",
    "su",
    "il",
    "la",
    "lo",
    "i",
    "gli",
    "le",
    "un",
}
TRAILING |= {"the", "of", "and", "in", "on", "a", "an", "to", "for"}


def short_title(source: Any) -> str:
    """The main title (before a colon or full stop); a long one is cut to
    five words, never ending on an article or preposition."""
    words = re.split(r"[:.?!]", _title(source), maxsplit=1)[0].split()
    if len(words) <= 7:
        return " ".join(words)
    words = words[:5]
    while len(words) > 1 and words[-1].casefold() in TRAILING:
        words.pop()
    return " ".join(words)


def in_text_names(source: Any) -> str:
    """How the sentence names a work: authors' surnames or its short title."""
    authors = _authors(source)
    if authors:
        return join_names([surname(a) for a in authors])
    return f"*{short_title(source)}*"


def _locator(label: str | None, pages: str | None) -> str | None:
    if not label:
        return None
    return label + ". " + re.sub(r"\s*[-–]\s*", "–", pages)


def full_reference(source: Any, web: dict[str, str] | None = None) -> str:
    """Nome Cognome, *Titolo*, in «Rivista», anno — without the final period."""
    authors = _authors(source)
    parts = [join_names([display_name(a) for a in authors])] if authors else []
    parts.append(f"*{_title(source)}*")
    if web:
        parts.append(f"in «{web['site']}»")
        parts.append(f"{web['url']} (ultima consultazione: {web['accessed']})")
        return ", ".join(parts)
    venue = " ".join(unescape(str(getattr(source, "venue", None) or "")).split())
    if venue and not REPOSITORY.search(venue):
        parts.append(f"in «{venue}»")
    if getattr(source, "year", None):
        parts.append(str(source.year))
    return ", ".join(parts)


def bibliography_entry(source: Any, web: dict[str, str] | None = None) -> str:
    entry = full_reference(source, web)
    if not web and getattr(source, "doi", None):
        entry += f", doi: {source.doi}"
    elif not web and getattr(source, "url", None):
        entry += f", {source.url}"
    return entry + "."


def render_notes(
    texts: list[str],
    known: dict[str, Any],
    web: dict[str, dict[str, str]] | None = None,
) -> tuple[list[str], list[str], dict[str, dict[str, Any]], list[str]]:
    """Replace the markers of all sections, in order, by numbered note
    placeholders. Returns the texts, the note texts (note n = notes[n - 1]),
    the bibliography entries of the cited works and the unknown keys."""
    web = web or {}
    texts = [normalize_locators(t) for t in texts]
    if known:
        # A key written as a word ("le fonti Site22026 e Site32021") is a
        # noun of the sentence: its authors' surnames carry the note.
        bare = re.compile(
            r"(?<![\[\w])("
            + "|".join(map(re.escape, sorted(known, key=len, reverse=True)))
            + r")(?![\]\w])"
        )
        texts = [
            bare.sub(lambda m: in_text_names(known[m.group(1)]) + f"[{m.group(1)}]", t)
            for t in texts
        ]
    cited = [k for t in texts for k in dict.fromkeys(CITE.findall(t)) if k[0] in known]
    first_surnames: dict[str, set[str]] = {}
    for key, *_ in cited:
        names = _authors(known[key]) or [_title(known[key])]
        first_surnames.setdefault(surname(names[0]), set()).add(key)
    notes: list[str] = []
    entries: dict[str, dict[str, Any]] = {}
    missing: list[str] = []
    seen: set[str] = set()
    previous: tuple[str, str | None] | None = None

    def cite(key: str, locator: str | None) -> str:
        source = known[key]
        link = web.get(key)
        locator = None if link else locator
        if key not in seen:
            seen.add(key)
            text = full_reference(source, link)
        else:
            names = [surname(a) for a in _authors(source)] or [short_title(source)]
            short = join_names(names)
            if len(first_surnames.get(surname(names[0]), ())) > 1:
                text = f"{short}, *{short_title(source)}*, cit."
            else:
                text = f"{short}, op. cit."
        return f"{text}, {locator}" if locator else text

    def note_for(group: list[re.Match[str]]) -> str | None:
        nonlocal previous
        rows = [
            (m.group(1), _locator(m.group(2), m.group(3)))
            for m in group
            if m.group(1) in known
        ]
        if not rows:
            previous = None
            return None
        if len(rows) == 1 and previous and previous[0] == rows[0][0]:
            key, locator = rows[0]
            locator = None if key in web else locator
            text = (
                "Ibidem"
                if locator == previous[1]
                else f"Ibid., {locator}"
                if locator
                else "Ibid."
            )
        else:
            text = "; ".join(cite(k, loc) for k, loc in rows)
        previous = rows[0] if len(rows) == 1 else None
        if previous and previous[0] in web:
            previous = (previous[0], None)
        for key, _ in rows:
            source = known[key]
            link = web.get(key)
            formatted = bibliography_entry(source, link)
            meta = source.canonical_metadata or {}
            entries.setdefault(
                key,
                {
                    "key": key,
                    "formatted": formatted,
                    "verified": True,
                    "verification_provider": meta.get("verification_provider"),
                    "origin": meta.get("origin", "pack"),
                    "kind": "web" if link else "academic",
                    "sort_key": sort_key(
                        surname((_authors(source) or [_title(source)])[0])
                        + " "
                        + formatted
                    ),
                },
            )
        notes.append(text[:1].upper() + text[1:] + ("" if text.endswith(".") else "."))
        return _note(len(notes))

    out_texts = []
    for text in texts:
        matches = list(CITE.finditer(text))
        groups: list[list[re.Match[str]]] = []
        for m in matches:
            if groups and re.fullmatch(
                r"[\s;,]*", text[groups[-1][-1].end() : m.start()]
            ):
                groups[-1].append(m)
            else:
                groups.append([m])
        out, pos = "", 0
        for group in groups:
            before = text[pos : group[0].start()]
            end = group[-1].end()
            for m in group:
                if m.group(1) not in known:
                    missing.append(m.group(1))
            wrapped = re.search(r"\(\s*$", before) and re.match(r"\s*\)", text[end:])
            if wrapped:
                before = before[: before.rstrip().rfind("(")]
                end += re.match(r"\s*\)", text[end:]).end()
            noun = bool(NOUN_BEFORE.search(before)) and not wrapped
            mark = note_for(group)
            if mark is None:
                out += (
                    before.rstrip() if re.match(r"\s*[.,;:!?)]", text[end:]) else before
                )
            elif noun:
                keys = [m.group(1) for m in group if m.group(1) in known]
                names = [in_text_names(known[k]) for k in keys]
                out += before + join_names(names) + mark
            else:
                out += before.rstrip() + mark
            pos = end
        out_texts.append(out + text[pos:])
    return out_texts, notes, entries, missing
