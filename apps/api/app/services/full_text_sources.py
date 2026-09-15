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
from app.services.model_recording import ReplayIncomplete
from app.services.replay_dependencies import recorded_dependency
from app.services.section_material import MAX_ACADEMIC_DOCUMENTS, MAX_SECTION_DOCUMENTS
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
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0 Safari/537.36 Thesica/1.0"
)
ACCEPT = "application/pdf,text/html;q=0.9,*/*;q=0.8"
_PDF_META_RE = re.compile(
    r"<meta[^>]+?(?:name|property)=[\"']citation_pdf_url[\"'][^>]*?"
    r"content=[\"']([^\"']+)[\"']"
    r"|<meta[^>]+?content=[\"']([^\"']+)[\"'][^>]*?"
    r"(?:name|property)=[\"']citation_pdf_url[\"']",
    re.I,
)


def open_access_url(work: dict[str, Any], provider: str) -> str | None:
    """The provider's own open-access PDF link, or None (Crossref has none)."""
    if provider == "openalex":
        best = work.get("best_oa_location") or {}
        url = best.get("pdf_url") or (work.get("open_access") or {}).get("oa_url")
    elif provider == "semantic_scholar":
        url = (work.get("openAccessPdf") or {}).get("url")
    else:
        url = None
    if isinstance(url, str) and url.startswith(("http://", "https://")):
        return url
    return None


def open_access_metadata(work: dict[str, Any], provider: str) -> dict[str, Any] | None:
    url = open_access_url(work, provider)
    return {"open_access_url": url} if url else None


def open_access_link(row: Any) -> str | None:
    """The stored open-access link of a search row dict or a SourceDoc."""
    metadata = (
        row.get("canonical_metadata")
        if isinstance(row, dict)
        else getattr(row, "canonical_metadata", None)
    )
    url = (metadata or {}).get("open_access_url")
    return url if isinstance(url, str) and url else None


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
    async with httpx.AsyncClient(
        timeout=FETCH_TIMEOUT_SECONDS,
        follow_redirects=True,
        headers={"User-Agent": USER_AGENT, "Accept": ACCEPT},
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
            pages = extract_pdf_pages(body)
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

    Returns the per-source summary and the keys that stay on their abstract.
    The frozen excerpt of a fetched source is rebuilt from abstract plus the
    pages closest to the topic; the writer's windows come from the passages.
    """

    async def fetched(row):
        link = open_access_link(row.source)
        async with semaphore:
            try:
                result = await full_text(link)
            except (RecordingPersistenceError, ReplayIncomplete):
                raise
            except Exception:
                result = {"pages": [], "reason": "transport_error"}
        return row, result, document_windows(row.citation_key, link, result["pages"])

    unavailable: list[str] = []
    summary: list[dict[str, Any]] = []
    for row, result, windows in await asyncio.gather(
        *(fetched(r) for r in selected if open_access_link(r.source))
    ):
        if windows:
            passages.extend(windows)
            freeze_evidence(row.source, passages, row.citation_key, query=topic)
            row.source.canonical_metadata.update(
                evidence_level="pdf",
                full_text={
                    "origin": "open_access",
                    "url": result.get("final_url") or open_access_link(row.source),
                    "pages": len(result["pages"]),
                    "windows": len(windows),
                    "chars": sum(len(w.text) for w in windows),
                },
            )
        else:
            unavailable.append(row.citation_key)
        summary.append(
            {
                "key": row.citation_key,
                "url": open_access_link(row.source),
                "pages": len(result["pages"]),
                "windows": len(windows),
                "reason": result.get("reason"),
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
    queries = section_queries(section, nodes)
    specific = (section_queries(section, []) or [""])[0]
    specific_terms = set(content_terms(specific))
    planned: list[str] = []
    excerpts: dict[str, str] = {}
    scored: list[tuple[float, int, str, bool, list, float]] = []
    for position, key in enumerate(section["evidence_keys"]):
        packed = pack.by_key(key)
        excerpt = evidence_text(packed.source) if packed else None
        if not excerpt:
            continue
        planned.append(packed.citation_key)
        excerpts[packed.citation_key] = excerpt
        ranked, best = _ranked(windows.get(packed.citation_key, []), queries)
        if ranked:
            scored.append((-(best + PLANNED_BONUS), position, key, True, ranked, best))
    for key, rows in windows.items():
        packed = pack.by_key(key)
        if key in planned or packed is None or not evidence_text(packed.source):
            continue
        gate, _, window = max(
            (score_passage(specific, w.text), -i, w) for i, w in enumerate(rows)
        )
        matched = len(specific_terms & set(content_terms(window.text)))
        ranked, best = _ranked(rows, queries)
        if ranked and gate >= MIN_RELEVANCE and matched >= MIN_MATCHED_TERMS:
            scored.append((-best, len(planned), key, False, ranked, best))
    # Primary sources (statutes, judgments, acts) first; academic commentary
    # after them, at most MAX_ACADEMIC_DOCUMENTS per section and, across the
    # work, no commentary document in more than a third of the sections.
    scored.sort(
        key=lambda t: (not is_legal_source(pack.by_key(t[2]).source), t[0], t[1], t[2])
    )
    budget = commentary if commentary is not None else {"cap": 10**6, "used": {}}
    chosen_docs, academic = [], 0
    for row in scored:
        key = row[2]
        if len(chosen_docs) >= MAX_SECTION_DOCUMENTS:
            break
        if not is_legal_source(pack.by_key(key).source):
            if (
                academic >= MAX_ACADEMIC_DOCUMENTS
                or budget["used"].get(key, 0) >= budget["cap"]
            ):
                continue
            academic += 1
            budget["used"][key] = budget["used"].get(key, 0) + 1
        chosen_docs.append(row)
    capped = {key for _, _, key, *_ in scored} - {row[2] for row in chosen_docs}
    queues = {key: list(ranked) for _, _, key, _, ranked, _ in chosen_docs}
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
                and bool(windows.get(key))
                and not chosen
                and key not in capped,
                "capped": key in capped,
            }
        )

    for _, _, key, is_planned, _, best in chosen_docs:
        chosen = sorted(taken[key], key=lambda t: t[0])
        if chosen:
            add(key, is_planned, render_windows(chosen), chosen, best)
        elif is_planned:
            add(key, True, excerpts[key], [], best)
    for key in planned:
        if key not in {r["key"] for r in report}:
            _, best = _ranked(windows.get(key, []), queries)
            add(key, True, excerpts[key], [], best)
    return items, report
