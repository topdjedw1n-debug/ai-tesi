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
from collections import Counter
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
CATALOGUE = re.compile(r"openalex\.org|semanticscholar\.org|crossref\.org", re.I)
# A book's venue is its publisher: "Open Book Publishers, 2009", not "in «…»".
PUBLISHER = re.compile(
    r"\b(?:publishers?|press|books|edizioni|editore|editrice|verlag|éditions)\b", re.I
)
# "Monaco colloca …", "Wiblin osserva …" (Antonioni order, 24.09): a name
# with a reporting verb in the sentence of the note.
REPORTED = re.compile(
    r"\b([A-Z][\w’'-]+)\s+(?:osserva|colloca|lega|sostiene|scrive|nota|afferma|"
    r"definisce|descrive|ricorda|individua|propone|sottolinea|rileva|parla|"
    r"considera|interpreta|analizza|spiega|suggerisce|attribuisce|legge|"
    r"collega|distingue|equipara)\b"
    # "vi è chi, come Fernaldo Di Giammatteo, la ritenne …"
    r"|\bcome\s+((?:[A-Z][\w’'-]+\s+)?(?:(?:Di|De|Del|Della|Da|Van|Von)\s+)?"
    r"[A-Z][\w’'-]+)\s*,"
)
NOT_NAMES = set(
    "il lo la i gli le un uno una questo questa questi queste quello quella "
    "ogni tale tali nessuna ciascuna alcuni alcune molti molte tutto tutti chi "
    "che cosa dove come quando anche già non più ne si ci la lettura fonte".split()
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


PAGE_NUMBER = re.compile(r"(?<![\d/.,-])(\d{1,4})(?![\d/.,%-])")


def printed_pages(pages: list[str], window: int = 6) -> dict[int, int]:
    """PDF page index -> the number printed on that page.

    Antonioni order (24.09): the writer's "p. 3" is the third page of the PDF,
    and the article is printed as pp. 269-279 (p. 3 is p. 271); Cardinali's
    thesis restarts its offset by section. A number at the head or foot of a
    page counts when the neighbouring pages agree on the same offset; a page
    without such agreement is left out of the map.
    """
    offsets = []
    for index, text in enumerate(pages, 1):
        words = text.split()
        edge = " ".join(words[:12] + ["|"] + words[-6:])
        offsets.append({int(n) - index for n in PAGE_NUMBER.findall(edge)})
    need = min(4, len(pages))
    mapped = {}
    for index in range(1, len(pages) + 1):
        votes = Counter(
            offset
            for j in range(max(1, index - window), min(len(pages), index + window) + 1)
            for offset in offsets[j - 1]
        )
        top = votes.most_common(2)
        second = top[1][1] if len(top) > 1 else 0
        if top and top[0][1] >= need and top[0][1] >= 2 * second:
            mapped[index] = index + top[0][0]
    return mapped


def _renumber(pages: str | None, page_map: dict[Any, Any] | None) -> str | None:
    """The printed numbers of a PDF locator, when every page of it is mapped."""
    if not pages or not page_map:
        return pages
    mapping = {int(k): int(v) for k, v in page_map.items()}
    numbers = [int(n) for n in re.findall(r"\d+", pages)]
    if not all(n in mapping for n in numbers):
        return pages
    return re.sub(r"\d+", lambda m: str(mapping[int(m.group(0))]), pages)


def _locator(label: str | None, pages: str | None) -> str | None:
    if not label:
        return None
    return label + ". " + re.sub(r"\s*[-–]\s*", "–", pages)


# Record types of Crossref and OpenAlex -> the four reference forms of the
# Vademecum (book, article, chapter in a volume, thesis).
TYPES = {
    "journal-article": "article",
    "article": "article",
    "review": "article",
    "preprint": "article",
    "posted-content": "article",
    "book-chapter": "chapter",
    "book-section": "chapter",
    "book-part": "chapter",
    "proceedings-article": "chapter",
    "book": "book",
    "monograph": "book",
    "edited-book": "book",
    "reference-book": "book",
    "dissertation": "thesis",
}


def _first(values: Any) -> Any:
    return next((v for v in values or [] if v), None)


def crossref_detail(message: dict[str, Any]) -> dict[str, Any]:
    """The reference fields of a Crossref work record."""
    issued = (
        ((message.get("issued") or {}).get("date-parts") or [[None]])[0] or [None]
    )[0]
    detail = {
        "type": TYPES.get(message.get("type")),
        "container": _first(message.get("container-title")),
        "volume": message.get("volume"),
        "issue": message.get("issue"),
        "pages": message.get("page"),
        "publisher": message.get("publisher"),
        "place": message.get("publisher-location"),
        "editors": [
            " ".join(p for p in (e.get("given"), e.get("family")) if p)
            for e in message.get("editor") or []
        ],
        "institution": _first(i.get("name") for i in message.get("institution") or []),
        "year": issued,
    }
    return {k: v for k, v in detail.items() if v}


def openalex_detail(work: dict[str, Any]) -> dict[str, Any]:
    """The reference fields of an OpenAlex work record."""
    biblio = work.get("biblio") or {}
    source = (work.get("primary_location") or {}).get("source") or {}
    kind = TYPES.get(work.get("type"))
    detail = {
        "type": kind,
        "container": source.get("display_name")
        if source.get("type") in ("journal", "book series", "conference")
        else None,
        "volume": biblio.get("volume"),
        "issue": biblio.get("issue"),
        "pages": "–".join(
            p for p in (biblio.get("first_page"), biblio.get("last_page")) if p
        ),
        "publisher": source.get("host_organization_name")
        if kind in ("book", "chapter")
        else None,
        "institution": _first(
            i.get("display_name")
            for a in work.get("authorships") or []
            for i in a.get("institutions") or []
        ),
        "year": work.get("publication_year"),
    }
    return {k: v for k, v in detail.items() if v}


def _imprint(detail: dict[str, Any], venue: str, year: Any) -> str:
    """Editore, Città Anno (the Vademecum puts no comma before the year)."""
    publisher = detail.get("publisher") or (venue if PUBLISHER.search(venue) else "")
    place_year = " ".join(str(p) for p in (detail.get("place"), year) if p)
    return ", ".join(p for p in (publisher, place_year) if p)


def full_reference(
    source: Any,
    web: dict[str, str] | None = None,
    detail: dict[str, Any] | None = None,
    locator: str | None = None,
) -> str:
    """The Vademecum reference without the final period. Book: Nome Cognome,
    *Titolo*, Editore, Città Anno; article: in «Rivista», vol. V, n. I (Anno),
    pp.; chapter: in Curatori (a cura di), *Volume*, Editore, Città Anno, pp.;
    thesis: tesi di dottorato, Istituzione, Anno. In a note the page locator
    replaces the page range."""
    detail = detail or {}
    authors = _authors(source)
    parts = [join_names([display_name(a) for a in authors])] if authors else []
    parts.append(f"*{detail.get('title') or _title(source)}*")
    if web:
        parts.append(f"in «{web['site']}»")
        parts.append(f"{web['url']} (ultima consultazione: {web['accessed']})")
        return ", ".join(parts)
    venue = " ".join(unescape(str(getattr(source, "venue", None) or "")).split())
    year = detail.get("year") or getattr(source, "year", None)
    kind = detail.get("type")
    container = " ".join(unescape(str(detail.get("container") or venue)).split())
    pages = detail.get("pages")
    if kind == "article" and container and not REPOSITORY.search(container):
        numbers = [f"vol. {detail['volume']}"] if detail.get("volume") else []
        numbers += [f"n. {detail['issue']}"] if detail.get("issue") else []
        head = ", ".join([f"in «{container}»", *numbers])
        parts.append(f"{head} ({year})" if year else head)
    elif kind == "chapter" and container:
        editors = detail.get("editors")
        curated = f"{join_names(editors)} (a cura di), " if editors else ""
        parts.append(f"in {curated}*{container}*")
        parts.append(_imprint(detail, venue, year))
    elif kind == "book":
        parts.append(_imprint(detail, venue, year))
    elif kind == "thesis":
        parts.append(detail.get("degree") or "tesi di dottorato")
        parts += [str(p) for p in (detail.get("institution"), year) if p]
    else:
        pages = None
        if venue and PUBLISHER.search(venue):
            parts.append(venue)
        elif venue and not REPOSITORY.search(venue):
            parts.append(f"in «{venue}»")
        if year:
            parts.append(str(year))
    if locator:
        parts.append(locator)
    elif pages and kind in ("article", "chapter"):
        parts.append("pp. " + re.sub(r"\s*[-–]\s*", "–", str(pages)))
    return ", ".join(p for p in parts if p)


def bibliography_entry(
    source: Any, web: dict[str, str] | None = None, detail: dict[str, Any] | None = None
) -> str:
    entry = full_reference(source, web, detail)
    if not web and getattr(source, "doi", None):
        entry += f", doi: {source.doi}"
    elif not web:
        # A catalogue record (openalex.org/W…) is no address for a reader.
        meta = source.canonical_metadata or {}
        link = meta.get("open_access_url") or getattr(source, "url", None)
        if link and not CATALOGUE.search(link):
            entry += f", {link}"
    return entry + "."


def render_notes(
    texts: list[str],
    known: dict[str, Any],
    web: dict[str, dict[str, str]] | None = None,
    details: dict[str, dict[str, Any]] | None = None,
    subject: tuple[str, ...] = (),
) -> tuple[list[str], list[str], dict[str, dict[str, Any]], list[str]]:
    """Replace the markers of all sections, in order, by numbered note
    placeholders. Returns the texts, the note texts (note n = notes[n - 1]),
    the bibliography entries of the cited works and the unknown keys.

    ``details`` are the reference fields per key (crossref_detail,
    openalex_detail, verified additions); ``subject`` names the people the
    work is about ("antonioni"), who are never someone's quoted source."""
    web = web or {}
    details = details or {}
    subject_names = {s.casefold() for s in subject}
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
            return full_reference(source, link, details.get(key), locator)
        else:
            names = [surname(a) for a in _authors(source)] or [short_title(source)]
            short = join_names(names)
            if len(first_surnames.get(surname(names[0]), ())) > 1:
                text = f"{short}, *{short_title(source)}*, cit."
            else:
                text = f"{short}, op. cit."
        return f"{text}, {locator}" if locator else text

    def note_for(group: list[re.Match[str]], quoted: str | None) -> str | None:
        nonlocal previous
        rows = [
            (
                m.group(1),
                _locator(
                    m.group(2),
                    _renumber(
                        m.group(3), (details.get(m.group(1)) or {}).get("page_map")
                    ),
                ),
            )
            for m in group
            if m.group(1) in known
        ]
        if not rows:
            previous = None
            return None
        if quoted:
            # The sentence names the author the source quotes (Kolker quoting
            # Monaco): "Monaco, cit. in Kolker, …", never an Ibid. chain.
            text = f"{quoted}, cit. in " + "; ".join(cite(k, loc) for k, loc in rows)
        elif len(rows) == 1 and previous and previous[0] == rows[0][0]:
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
        previous = rows[0] if len(rows) == 1 and not quoted else None
        if previous and previous[0] in web:
            previous = (previous[0], None)
        for key, _ in rows:
            source = known[key]
            link = web.get(key)
            formatted = bibliography_entry(source, link, details.get(key))
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
            sentence = re.split(r"(?<=[.!?])\s+", out + before)[-1]
            said = REPORTED.search(sentence)
            authors = {
                surname(a).casefold()
                for m in group
                if m.group(1) in known
                for a in _authors(known[m.group(1)])
            }
            name = (said.group(1) or said.group(2)) if said else ""
            quoted = (
                name
                if said
                and surname(name).casefold() not in authors | subject_names | NOT_NAMES
                and "\ue000" not in sentence[said.end() :]  # the first note after it
                and not noun
                else None
            )
            mark = note_for(group, quoted)
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
