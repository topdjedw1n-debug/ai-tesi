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
from app.services.model_recording import ReplayIncomplete
from app.services.replay_dependencies import recorded_dependency
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
    pack: Any, section: dict[str, Any], nodes: list[dict[str, Any]]
) -> tuple[list[dict[str, str]], list[dict[str, Any]]]:
    """Prompt evidence for one section and the selection report behind it.

    Planned documents (S3 order) come first, then manager-uploaded documents
    the plan did not assign when one of their windows covers the section's own
    wording well enough (fetched open-access texts count only where the plan
    put them: their relevance is not vetted by anyone). Windows are
    allocated round-robin across the documents, most relevant first, so every
    document keeps a minimal share before any of them expands (M1: the
    judgment needed many windows next to a one-page statute). A planned
    document without a relevant window keeps its frozen excerpt exactly as
    before and is reported as a gap; documents without full text keep it too.
    """
    windows: dict[str, list[SourcePassage]] = {}
    for passage in getattr(pack, "passages", None) or []:
        windows.setdefault(passage.citation_key, []).append(passage)
    queries = section_queries(section, nodes)
    specific = (section_queries(section, []) or [""])[0]
    specific_terms = set(content_terms(specific))
    order: list[tuple[str, bool, list, float, str | None]] = []
    planned: list[str] = []
    for key in section["evidence_keys"]:
        packed = pack.by_key(key)
        excerpt = evidence_text(packed.source) if packed else None
        if not excerpt:
            continue
        planned.append(packed.citation_key)
        ranked, best = _ranked(windows.get(packed.citation_key, []), queries)
        order.append((key, True, ranked, best, excerpt))
    candidates = []
    for key, rows in windows.items():
        packed = pack.by_key(key)
        if (
            key in planned
            or packed is None
            or packed.source.provider != "uploaded"
            or not evidence_text(packed.source)
        ):
            continue
        gate, _, window = max(
            (score_passage(specific, w.text), -i, w) for i, w in enumerate(rows)
        )
        matched = len(specific_terms & set(content_terms(window.text)))
        ranked, best = _ranked(rows, queries)
        if ranked and gate >= MIN_RELEVANCE and matched >= MIN_MATCHED_TERMS:
            candidates.append((-gate, key, ranked, best))
    for _, key, ranked, best in sorted(candidates, key=lambda t: (t[0], t[1])):
        order.append((key, False, ranked, best, None))
    queues = {key: list(ranked) for key, _, ranked, _, _ in order}
    taken: dict[str, list[tuple[int, SourcePassage]]] = {key: [] for key in queues}
    doc_chars = dict.fromkeys(queues, 0)
    used = 0
    while used < SECTION_EVIDENCE_CHARS:
        progressed = False
        for key, *_ in order:
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
    for key, is_planned, _, best, excerpt in order:
        chosen = sorted(taken[key], key=lambda t: t[0])
        if chosen:
            text = render_windows(chosen)
        elif is_planned:
            text = excerpt
        else:
            continue
        items.append({"key": key, "text": text})
        report.append(
            {
                "key": key,
                "planned": is_planned,
                "windows": len(chosen),
                "pages": sorted({w.page_number for _, w in chosen}),
                "chars": len(text),
                "score": round(best, 4),
                "gap": is_planned and bool(windows.get(key)) and not chosen,
            }
        )
    return items, report
