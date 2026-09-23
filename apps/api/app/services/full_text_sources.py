"""Full-text evidence: open-access PDFs and page-anchored windows per section.

Stage "material in S2" (2026-09-14). A source stays one citation key and one
bibliography entry. Its full text lives as page-bounded windows in
``pack.passages`` (the same ``SourcePassage`` shape as manager-uploaded PDFs).
Each section receives only the windows relevant to its plan, labelled
``[page N]`` so the writer cites ``[KEY] p. N``; there are no fragment keys.
"""

from __future__ import annotations

import asyncio
import re
from typing import Any

import httpx

from app.services.generation_policy import RecordingPersistenceError
from app.services.legal_sources import is_legal_source
from app.services.material_fit import (
    MIN_DOCUMENT_TOPIC_SHARE,
    about_section,
    document_topic_share,
)
from app.services.model_recording import ReplayIncomplete
from app.services.replay_dependencies import recorded_dependency
from app.services.search_queries import anchors, english_core
from app.services.section_material import (
    MAX_ACADEMIC_DOCUMENTS,
    MAX_LEGAL_WINDOWS,
    MAX_SECTION_DOCUMENTS,
)
from app.services.source_evidence import evidence_text, freeze_evidence
from app.services.uploaded_sources import (
    MAX_SOURCE_FILE_BYTES,
    MIN_TEXT_CHARS_PER_PAGE,
    SourcePassage,
    content_terms,
    extract_pdf_pages,
    score_passage,
    split_passages,
)

# Evidence budgets per section prompt, in characters. The M1 material test gave
# one section ~18k characters of full inputs (~4.5k tokens).
SECTION_EVIDENCE_CHARS = 20_000
DOCUMENT_EVIDENCE_CHARS = 16_000
# A manager-uploaded document the plan did not assign joins a section only when
# its best window covers the section's own wording (title, purpose, main
# points) this well and with this many distinct terms; scope terms alone gave
# false positives on off-topic English documents (calibration on B, 14.09).
MIN_RELEVANCE = 0.30
MIN_MATCHED_TERMS = 5
# Within one document, windows far below its best match are padding.
RELATIVE_FLOOR = 0.5
# The plan's judgment counts a little when documents tie on relevance.
PLANNED_BONUS = 0.05
# Overlapping windows share at most this many leading words.
MAX_OVERLAP_WORDS = 40
FETCH_TIMEOUT_SECONDS = 30.0
# Copies of the same work (17.09.2026, psychology): the fetch took one link,
# the provider's best open-access location, and Crossref records had none.
# The OpenAlex ``locations`` list names the repository copies too; every
# selected record tries at most this many links, the run at most this many.
MAX_LINKS_PER_SOURCE = 3
MAX_FULL_TEXT_TRIES = 60
OPENALEX_LOCATIONS_SELECT = "id,doi,open_access,best_oa_location,locations"
POLITE_MAILTO = "research@thesica.ai"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 Thesica/1.0"
)
# 24.09.2026, order 24286128: HAL answered the browser-like agent with its bot
# check ("Making sure you're not a bot!") but serves the same thesis PDF to a
# client that says what it is; a link that yields no PDF is asked once more
# under this declared agent.
DECLARED_AGENT = f"Thesica/1.0 (+mailto:{POLITE_MAILTO})"
ACCEPT = "application/pdf,text/html;q=0.9,*/*;q=0.8"
_PDF_META_RE = re.compile(
    r"<meta[^>]+?(?:name|property)=[\"']citation_pdf_url[\"'][^>]*?"
    r"content=[\"']([^\"']+)[\"']"
    r"|<meta[^>]+?content=[\"']([^\"']+)[\"'][^>]*?"
    r"(?:name|property)=[\"']citation_pdf_url[\"']",
    re.I,
)


def _http(url: Any) -> str | None:
    return (
        url
        if isinstance(url, str) and url.startswith(("http://", "https://"))
        else None
    )


def open_access_urls(work: dict[str, Any], provider: str) -> list[str]:
    """Every open-access link of the work the provider names, best first:
    PDF links of repository copies, then PDF links of the other copies, then
    the provider's best location; landing pages only when no PDF link exists
    (an HTML page is followed once through ``citation_pdf_url``). Crossref
    names none."""
    urls: list[str] = []

    def add(url: Any) -> None:
        link = _http(url)
        if link and link not in urls:
            urls.append(link)

    if provider == "openalex":
        locations = [
            loc for loc in work.get("locations") or [] if isinstance(loc, dict)
        ]
        open_locations = [loc for loc in locations if loc.get("is_oa")]
        repositories = [
            loc
            for loc in open_locations
            if (loc.get("source") or {}).get("type") == "repository"
        ]
        for loc in repositories + open_locations:
            add(loc.get("pdf_url"))
        best = work.get("best_oa_location") or {}
        add(best.get("pdf_url"))
        add((work.get("open_access") or {}).get("oa_url"))
        if not urls:
            for loc in repositories + open_locations:
                add(loc.get("landing_page_url"))
    elif provider == "semantic_scholar":
        add((work.get("openAccessPdf") or {}).get("url"))
    return urls


def open_access_url(work: dict[str, Any], provider: str) -> str | None:
    """The provider's first open-access link, or None (Crossref has none)."""
    urls = open_access_urls(work, provider)
    return urls[0] if urls else None


def open_access_metadata(work: dict[str, Any], provider: str) -> dict[str, Any] | None:
    urls = open_access_urls(work, provider)
    return {"open_access_url": urls[0], "open_access_urls": urls} if urls else None


def open_access_link(row: Any) -> str | None:
    """The stored open-access link of a search row dict or a SourceDoc."""
    metadata = (
        row.get("canonical_metadata")
        if isinstance(row, dict)
        else getattr(row, "canonical_metadata", None)
    )
    url = (metadata or {}).get("open_access_url")
    return url if isinstance(url, str) and url else None


def links_metadata(row: Any) -> dict[str, Any]:
    """The open-access fields to store for a row: its first link and the list."""
    urls = open_access_links(row)
    return {"open_access_url": urls[0], "open_access_urls": urls} if urls else {}


def open_access_links(row: Any) -> list[str]:
    """Every stored open-access link of a row, the single link included."""
    metadata = (
        row.get("canonical_metadata")
        if isinstance(row, dict)
        else getattr(row, "canonical_metadata", None)
    ) or {}
    urls = [u for u in metadata.get("open_access_urls") or [] if _http(u)]
    single = open_access_link(row)
    if single and single not in urls:
        urls.insert(0, single)
    return urls


@recorded_dependency("executor_locations")
async def open_access_locations(doi: str) -> dict[str, Any]:
    """The open-access copies OpenAlex lists for a DOI (Crossref and Semantic
    Scholar records name at most one link; OpenAlex names them all)."""
    from app.core.config import settings

    base = str(getattr(settings, "OPENALEX_API_URL", "https://api.openalex.org"))
    key = getattr(settings, "OPENALEX_API_KEY", None)
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS, follow_redirects=True, headers=headers
    ) as client:
        response = await client.get(
            f"{base.rstrip('/')}/works/https://doi.org/{doi}",
            params={"select": OPENALEX_LOCATIONS_SELECT, "mailto": POLITE_MAILTO},
        )
    urls = (
        open_access_urls(response.json(), "openalex")
        if response.status_code == 200
        else []
    )
    return {"doi": doi, "status": response.status_code, "urls": urls}


async def _download(client: httpx.AsyncClient, url: str) -> tuple[Any, bytes, bool]:
    async with client.stream("GET", url) as response:
        chunks: list[bytes] = []
        size = 0
        async for chunk in response.aiter_bytes():
            size += len(chunk)
            if size > MAX_SOURCE_FILE_BYTES:
                return response, b"", True
            chunks.append(chunk)
        return response, b"".join(chunks), False


@recorded_dependency("executor_full_text")
async def full_text(url: str) -> dict[str, Any]:
    """Text pages behind an open-access link; refusals are data, not errors.

    Only transport failures propagate (and replay as recorded failures). An
    HTML landing page is followed once through its ``citation_pdf_url`` meta
    tag; paywalls, bot walls and scans without a text layer yield a reason.
    Page text is recorded instead of PDF bytes: replay needs the words.
    """
    result: dict[str, Any] = {
        "url": url,
        "final_url": None,
        "content_type": None,
        "pages": [],
        "reason": None,
    }
    for agent in (USER_AGENT, DECLARED_AGENT):
        async with httpx.AsyncClient(
            timeout=FETCH_TIMEOUT_SECONDS,
            follow_redirects=True,
            headers={"User-Agent": agent, "Accept": ACCEPT},
        ) as client:
            response, body, too_large = await _download(client, url)
            if (
                not too_large
                and response.status_code == 200
                and b"%PDF" not in body[:1024]
                and b"citation_pdf_url" in body
            ):
                match = _PDF_META_RE.search(body.decode("utf-8", "ignore"))
                link = next((g for g in (match.groups() if match else ()) if g), None)
                if link:
                    link = str(httpx.URL(str(response.url)).join(link))
                    response, body, too_large = await _download(client, link)
        if too_large or (response.status_code == 200 and b"%PDF" in body[:1024]):
            break
    result.update(
        final_url=str(response.url), content_type=response.headers.get("content-type")
    )
    if too_large:
        result["reason"] = "too_large"
    elif response.status_code != 200:
        result["reason"] = f"http_{response.status_code}"
    elif b"%PDF" not in body[:1024]:
        result["reason"] = "not_pdf"
    else:
        try:
            # pypdf is CPU-bound and synchronous; a heavy PDF must not block the
            # event loop (job 32, 17.09: the heartbeat starved and the lease
            # expired while S2 was reading the fetched copies).
            pages = await asyncio.to_thread(extract_pdf_pages, body)
        except ValueError as error:
            result["reason"] = f"unreadable_pdf: {error}"[:200]
            return result
        if not pages or sum(len(p) for p in pages) < MIN_TEXT_CHARS_PER_PAGE * len(
            pages
        ):
            result["reason"] = "no_text_layer"
        else:
            result["pages"] = pages
    return result


def document_windows(
    citation_key: str, url: str, pages: list[str]
) -> list[SourcePassage]:
    """Page-bounded windows of a fetched document, in document order."""
    return split_passages(
        source_file_id=0,
        citation_key=citation_key,
        filename=url,
        pages=list(enumerate(pages, 1)),
    )


async def attach_full_text(
    selected: list[Any], passages: list[SourcePassage], semaphore: Any, topic: str
) -> tuple[list[dict[str, Any]], list[str]]:
    """Fetch the open-access full texts of selected pack sources into passages.

    Returns the per-source summary and, for every record that stays on its
    abstract, "title — link" (order 24286128: the manager opens a link the
    site refused to the fetcher in a browser and adds the PDF by hand).
    The frozen excerpt of a fetched source is rebuilt from abstract plus the
    pages closest to the topic; the writer's windows come from the passages.
    """

    budget = {"tries": 0}

    async def links_of(row):
        """The record's links; a record without one asks OpenAlex once."""
        links = open_access_links(row.source)
        if links or not getattr(row.source, "doi", None):
            return links
        async with semaphore:
            try:
                found = await open_access_locations(row.source.doi)
            except (RecordingPersistenceError, ReplayIncomplete):
                raise
            except Exception:
                return []
        links = [u for u in found.get("urls") or [] if _http(u)]
        if links:
            row.source.canonical_metadata.update(
                open_access_url=links[0], open_access_urls=links
            )
        return links

    async def fetched(row):
        tries: list[dict[str, Any]] = []
        result: dict[str, Any] = {"pages": [], "reason": "no_link"}
        link = None
        for link in (await links_of(row))[:MAX_LINKS_PER_SOURCE]:
            async with semaphore:
                if budget["tries"] >= MAX_FULL_TEXT_TRIES:
                    result = {"url": link, "pages": [], "reason": "budget"}
                    tries.append({"url": link, "pages": 0, "reason": "budget"})
                    break
                budget["tries"] += 1
                try:
                    result = await full_text(link)
                except (RecordingPersistenceError, ReplayIncomplete):
                    raise
                except Exception:
                    result = {"url": link, "pages": [], "reason": "transport_error"}
            tries.append(
                {
                    "url": link,
                    "pages": len(result["pages"]),
                    "reason": result.get("reason"),
                }
            )
            if result["pages"]:
                break
        windows = (
            document_windows(row.citation_key, link, result["pages"]) if link else []
        )
        return row, result, windows, tries

    unavailable: list[str] = []
    summary: list[dict[str, Any]] = []
    for row, result, windows, tries in await asyncio.gather(
        *(fetched(r) for r in selected)
    ):
        if not tries:
            continue  # no link at all: the record stays on its abstract
        if windows:
            passages.extend(windows)
            freeze_evidence(row.source, passages, row.citation_key, query=topic)
            row.source.canonical_metadata.update(
                evidence_level="pdf",
                full_text={
                    "origin": "open_access",
                    "url": result.get("final_url") or tries[-1]["url"],
                    "pages": len(result["pages"]),
                    "windows": len(windows),
                    "chars": sum(len(w.text) for w in windows),
                },
            )
        else:
            unavailable.append(f"{row.source.title} — {tries[-1]['url']}")
        summary.append(
            {
                "key": row.citation_key,
                "url": tries[-1]["url"],
                "pages": len(result["pages"]),
                "windows": len(windows),
                "reason": result.get("reason"),
                "tries": tries,
            }
        )
    return summary, unavailable


def section_queries(section: dict[str, Any], nodes: list[dict[str, Any]]) -> list[str]:
    """What the section is about, one query per language.

    A mixed-language query would dilute the score of every fragment: the plan
    text and the local scope terms form one query, the English scope terms
    another, and a window scores by its best match.
    """
    by_id = {n.get("scope_id"): n for n in nodes}
    local = [
        section.get("title"),
        section.get("purpose"),
        section.get("question"),
        *section.get("main_points", []),
    ]
    english: list[Any] = []
    for scope_id in section.get("scope_ids", []):
        node = by_id.get(scope_id) or {}
        local += list(node.get("terms_local", []))
        english += list(node.get("terms_en", []))
    queries = []
    for terms in (local, english):
        query = " ".join(t for t in terms if isinstance(t, str) and t.strip())
        if query:
            queries.append(query)
    return queries


def relevance(queries: list[str], text: str) -> float:
    return max((score_passage(q, text) for q in queries), default=0.0)


def _ranked(
    windows: list[SourcePassage], queries: list[str]
) -> tuple[list[tuple[int, SourcePassage]], float]:
    scored = [(relevance(queries, w.text), i, w) for i, w in enumerate(windows)]
    best = max((s for s, _, _ in scored), default=0.0)
    ranked = [
        (i, w)
        for s, i, w in sorted(scored, key=lambda t: (-t[0], t[1]))
        if s > 0 and s >= RELATIVE_FLOOR * best
    ]
    return ranked, best


def _join_overlap(left: str, right: str) -> str:
    """Consecutive windows repeat a tail of the previous one; keep it once."""
    words = right.split()
    for count in range(min(len(words), MAX_OVERLAP_WORDS), 0, -1):
        head = " ".join(words[:count])
        if left.endswith(head):
            return left + right[len(head) :]
    return left + " " + right


def render_windows(chosen: list[tuple[int, SourcePassage]]) -> str:
    """Windows in document order, adjacent ones merged, each block page-labelled."""
    blocks: list[tuple[int, int, str]] = []
    for index, window in chosen:
        if (
            blocks
            and index == blocks[-1][0] + 1
            and window.page_number == blocks[-1][1]
        ):
            _, page, text = blocks[-1]
            blocks[-1] = (index, page, _join_overlap(text, window.text))
        else:
            blocks.append((index, window.page_number, window.text))
    return "\n".join(f"[page {page}] {text}" for _, page, text in blocks)


def topic_pattern(pack: Any, nodes: list[dict[str, Any]]) -> re.Pattern[str] | None:
    """The topic anchors of the work (the S2 on-topic pattern)."""
    return anchors(str(getattr(pack, "topic", "") or ""), english_core(nodes, 8))


def full_text_usable(
    pack: Any, key: str, nodes: list[dict[str, Any]], pattern: Any = None
) -> bool:
    """A document's pages serve the work only when enough of them are about
    the topic; a same-field text on another question (an HIV-integrase
    thesis in a run on antibiotic resistance) keeps its abstract at most."""
    packed = pack.by_key(key) if hasattr(pack, "by_key") else None
    judgment = ((packed.source.canonical_metadata or {}) if packed else {}).get(
        "topic_judgment"
    ) or {}
    if judgment.get("verdict") == "reject":
        return False  # judged to be about another question (topic_judgment.py)
    windows = [
        p.text for p in getattr(pack, "passages", None) or [] if p.citation_key == key
    ]
    if not windows:
        return False
    pattern = pattern if pattern is not None else topic_pattern(pack, nodes)
    return document_topic_share(windows, pattern) >= MIN_DOCUMENT_TOPIC_SHARE


def section_evidence(
    pack: Any,
    section: dict[str, Any],
    nodes: list[dict[str, Any]],
    commentary: dict[str, Any] | None = None,
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Prompt evidence for one section and the selection report behind it.

    The section is written from at most ``MAX_SECTION_DOCUMENTS`` documents,
    primary sources (statutes, judgments, acts) before academic commentary
    (at most ``MAX_ACADEMIC_DOCUMENTS`` per section, and per ``commentary``
    budget no commentary document in more than a third of the sections):
    the planned ones (S3) and any other full-text document of the pack whose
    best window covers the section's own wording (title, purpose, main
    points) well enough, ranked by relevance with a small bonus for the plan.
    Depth over breadth: windows are allocated round-robin across the chosen
    documents, most relevant first, so every document keeps a minimal share
    before any of them expands (M1: the judgment needed many windows next to
    a one-page statute). A planned document without a relevant window keeps
    its frozen excerpt exactly as before and is reported as a gap; a planned
    document ranked below the cap keeps its excerpt and is reported as
    capped; documents without full text keep their excerpt too.
    """
    windows: dict[str, list[SourcePassage]] = {}
    for passage in getattr(pack, "passages", None) or []:
        windows.setdefault(passage.citation_key, []).append(passage)
    pattern = topic_pattern(pack, nodes)
    topic = str(getattr(pack, "topic", "") or "")
    had_windows = set(windows)
    off_topic = {
        key for key in windows if not full_text_usable(pack, key, nodes, pattern)
    }
    for key in off_topic:
        windows.pop(key)
    queries = section_queries(section, nodes)
    specific = (section_queries(section, []) or [""])[0]
    specific_terms = set(content_terms(specific))

    gates = [(specific, specific_terms)] + [
        (q, set(content_terms(q))) for q in queries[1:]
    ]  # the section's own wording, then the English terms of its nodes

    def window_gate(rows: list[SourcePassage]) -> bool:
        """The document's best window covers the section's own wording, in
        the plan's language or in the English terms of the section's nodes
        (off-topic full texts were already removed by the topic share)."""
        if not rows:
            return False
        for query, terms in gates:
            gate, _, window = max(
                (score_passage(query, w.text), -i, w) for i, w in enumerate(rows)
            )
            matched = len(terms & set(content_terms(window.text)))
            if gate >= MIN_RELEVANCE and matched >= MIN_MATCHED_TERMS:
                return True
        return False

    # One exam for every document, planned or not: about the section (its
    # nodes' own terms or the section's wording in title/abstract) or a best
    # window that covers the section's wording; anything else is unsuitable
    # and hands the writer neither pages nor its excerpt.
    planned: list[str] = []
    excerpts: dict[str, str] = {}
    reasons: dict[str, str] = {}
    scored: list[tuple[float, int, str, bool, list, float]] = []
    for position, key in enumerate(section["evidence_keys"]):
        packed = pack.by_key(key)
        excerpt = evidence_text(packed.source) if packed else None
        if not excerpt:
            continue
        rows = windows.get(packed.citation_key, [])
        fit = about_section(section, nodes, packed.source, topic)
        if not fit and not window_gate(rows):
            reasons[packed.citation_key] = (
                "off_topic_text" if packed.citation_key in off_topic else "unsuitable"
            )
            continue
        planned.append(packed.citation_key)
        excerpts[packed.citation_key] = excerpt
        reasons[packed.citation_key] = "support" if fit else "windows"
        ranked, best = _ranked(rows, queries)
        if ranked:
            scored.append((-(best + PLANNED_BONUS), position, key, True, ranked, best))
    for key, rows in windows.items():
        packed = pack.by_key(key)
        if key in planned or key in reasons or packed is None:
            continue
        if not evidence_text(packed.source):
            continue
        fit = about_section(section, nodes, packed.source, topic)
        if not fit and not window_gate(rows):
            continue
        ranked, best = _ranked(rows, queries)
        if ranked:
            reasons[key] = "support" if fit else "windows"
            scored.append((-best, len(planned), key, False, ranked, best))
    # Primary sources (statutes, judgments, acts) first; academic commentary
    # after them, at most MAX_ACADEMIC_DOCUMENTS per section and, across the
    # work, no commentary document in more than a third of the sections.
    # Primary sources first, then documents about the section before documents
    # that only have matching windows (the E2 book on cyber-risk regulation
    # led six sections while the crowdfunding records were abstracts).
    scored.sort(
        key=lambda t: (
            not is_legal_source(pack.by_key(t[2]).source),
            reasons.get(t[2]) != "support",
            t[0],
            t[1],
            t[2],
        )
    )
    budget = commentary if commentary is not None else {"cap": 10**6, "used": {}}
    # Commentary is rationed only where primary legal evidence competes with
    # it; in economics or computer science the articles are the evidence.
    academic_cap = (
        MAX_ACADEMIC_DOCUMENTS
        if any(is_legal_source(pack.by_key(t[2]).source) for t in scored)
        else MAX_SECTION_DOCUMENTS
    )
    chosen_docs, academic = [], 0
    for row in scored:
        key = row[2]
        if len(chosen_docs) >= MAX_SECTION_DOCUMENTS:
            break
        if not is_legal_source(pack.by_key(key).source):
            if academic >= academic_cap or budget["used"].get(key, 0) >= budget["cap"]:
                continue
            academic += 1
            budget["used"][key] = budget["used"].get(key, 0) + 1
        chosen_docs.append(row)
    capped = {key for _, _, key, *_ in scored} - {row[2] for row in chosen_docs}
    queues = {key: list(ranked) for _, _, key, _, ranked, _ in chosen_docs}
    legal = {key: is_legal_source(pack.by_key(key).source) for key in queues}
    taken: dict[str, list[tuple[int, SourcePassage]]] = {key: [] for key in queues}
    doc_chars = dict.fromkeys(queues, 0)
    used = 0
    while used < SECTION_EVIDENCE_CHARS:
        progressed = False
        for key in queues:
            queue = queues[key]
            if not queue:
                continue
            index, window = queue[0]
            size = len(window.text)
            if (
                doc_chars[key] + size > DOCUMENT_EVIDENCE_CHARS
                or used + size > SECTION_EVIDENCE_CHARS
                or (legal[key] and len(taken[key]) >= MAX_LEGAL_WINDOWS)
            ):
                queue.clear()
                continue
            queue.pop(0)
            taken[key].append((index, window))
            doc_chars[key] += size
            used += size
            progressed = True
        if not progressed:
            break
    items: list[dict[str, str]] = []
    report: list[dict[str, Any]] = []

    def add(key: str, is_planned: bool, text: str, chosen: list, best: float) -> None:
        if text:
            items.append({"key": key, "text": text})
        report.append(
            {
                "key": key,
                "planned": is_planned,
                "windows": len(chosen),
                "pages": sorted({w.page_number for _, w in chosen}),
                "chars": len(text),
                "score": round(best, 4),
                "gap": is_planned
                and key in had_windows
                and not chosen
                and key not in capped,
                "capped": key in capped,
                "reason": reasons.get(key, "unsuitable"),
            }
        )

    # Documents about the section come first, with their pages or their
    # excerpt; documents that only matched through windows follow with their
    # pages; a suitable planned document without pages keeps its excerpt (as
    # before); an unsuitable planned document is reported and hands nothing.
    ordered = [row for row in chosen_docs if reasons[row[2]] == "support"]
    ordered += [
        (0.0, position, key, True, [], _ranked(windows.get(key, []), queries)[1])
        for position, key in enumerate(planned)
        if reasons[key] == "support" and key not in {row[2] for row in chosen_docs}
    ]
    ordered += [row for row in chosen_docs if reasons[row[2]] != "support"]
    ordered += [
        (0.0, position, key, True, [], _ranked(windows.get(key, []), queries)[1])
        for position, key in enumerate(planned)
        if reasons[key] == "windows" and key not in {row[2] for row in chosen_docs}
    ]
    for _, _, key, is_planned, _, best in ordered:
        chosen = sorted(taken.get(key, []), key=lambda t: t[0])
        if chosen:
            add(key, is_planned, render_windows(chosen), chosen, best)
        elif is_planned:
            add(key, True, excerpts[key], [], best)
    for key, reason in reasons.items():
        if reason in ("unsuitable", "off_topic_text"):
            add(key, True, "", [], 0.0)
    return items, report


def selection_summary(selection: list[dict[str, Any]]) -> str:
    """Why a section has no pages, for the manager's warning."""
    counts: dict[str, int] = {}
    for row in selection:
        counts[row.get("reason", "")] = counts.get(row.get("reason", ""), 0) + 1
    labels = {
        "unsuitable": "не про питання розділу",
        "off_topic_text": "повний текст не про тему",
        "support": "про питання, але без повного тексту",
        "windows": "лише збіг вікон",
        "capped": "понад ліміт документів",
    }
    return "; ".join(f"{labels[k]}: {v}" for k, v in counts.items() if k in labels)
