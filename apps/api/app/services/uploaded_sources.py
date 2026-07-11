"""User-uploaded scientific PDFs as page-anchored grounding sources.

Stage "full-text evidence" (2026-07-11). External APIs give metadata and
abstracts; professor-mandated readings arrive as PDFs. This service parses
them page by page, derives honest citation metadata, and retrieves the
best passages for a query — each carrying (file, page) so a claim can be
traced to an exact excerpt.

No OCR: scanned PDFs without a text layer are stored but flagged
``no_text_layer`` and excluded from retrieval.
"""

from __future__ import annotations

import hashlib
import io
import logging
import re
import unicodedata
from dataclasses import dataclass

from pypdf import PdfReader
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.document import DocumentSourceFile, SourceFilePage

logger = logging.getLogger(__name__)

MAX_SOURCE_FILE_BYTES = 25 * 1024 * 1024
MAX_SOURCE_FILE_PAGES = 400
# Below this many characters per page on average, the PDF is a scan.
MIN_TEXT_CHARS_PER_PAGE = 120

# Passage shaping: big enough to carry an argument, small enough that a
# handful fit into a section prompt with their page labels.
PASSAGE_TARGET_CHARS = 900
PASSAGE_MIN_CHARS = 200

_YEAR_RE = re.compile(r"\b(19[5-9]\d|20[0-4]\d)\b")
_KEY_SANITIZE_RE = re.compile(r"[^0-9A-Za-z]+")
_WORD_RE = re.compile(r"[a-z0-9]{3,}")

# Italian/English function words that carry no retrieval signal.
_STOPWORDS = frozenset(
    """
    della delle degli dello nella nelle negli sulla sulle con per una uno
    che chi cui non più tra fra come sono stato stata stati state essere
    the and for with from this that are was were been have has its can
    del dei nel nei dal dai gli una alle allo all
    """.split()
)


def _normalize(text: str) -> str:
    """Lowercase, accent-strip, for language-tolerant lexical matching."""
    decomposed = unicodedata.normalize("NFKD", text.lower())
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def _terms(text: str) -> list[str]:
    return [t for t in _WORD_RE.findall(_normalize(text)) if t not in _STOPWORDS]


@dataclass(frozen=True)
class SourcePassage:
    """One retrievable excerpt with its exact provenance."""

    source_file_id: int
    citation_key: str
    filename: str
    page_number: int  # 1-based, as shown in a PDF reader
    text: str
    score: float = 0.0


def extract_pdf_pages(data: bytes) -> list[str]:
    """Per-page text, 1-based order preserved. Raises ValueError on limits."""
    if len(data) > MAX_SOURCE_FILE_BYTES:
        raise ValueError(
            f"PDF exceeds the {MAX_SOURCE_FILE_BYTES // (1024 * 1024)} MB limit"
        )
    try:
        reader = PdfReader(io.BytesIO(data))
    except Exception as exc:  # encrypted/corrupt
        raise ValueError(f"Not a readable PDF: {exc}") from exc
    if reader.is_encrypted:
        try:
            reader.decrypt("")
        except Exception as exc:
            raise ValueError("Encrypted PDF is not supported") from exc
    if len(reader.pages) > MAX_SOURCE_FILE_PAGES:
        raise ValueError(
            f"PDF has {len(reader.pages)} pages; limit is {MAX_SOURCE_FILE_PAGES}"
        )
    pages: list[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return pages


def derive_source_metadata(
    filename: str, data: bytes, pages: list[str]
) -> dict[str, object]:
    """Best-effort citation metadata; honesty over invention.

    Missing author/title/year never blocks the upload — the file is flagged
    ``metadata_incomplete`` so the manager corrects it before release
    instead of the system inventing bibliography fields.
    """
    title: str | None = None
    author: str | None = None
    try:
        meta = PdfReader(io.BytesIO(data)).metadata
        if meta:
            raw_title = (meta.title or "").strip()
            raw_author = (meta.author or "").strip()
            # PDF producers dump junk here; accept only plausible values.
            if 8 <= len(raw_title) <= 300 and not raw_title.lower().endswith(".dvi"):
                title = raw_title
            if 3 <= len(raw_author) <= 200:
                author = raw_author
    except Exception:
        pass

    stem = re.sub(r"\.pdf$", "", filename, flags=re.IGNORECASE)
    year: int | None = None
    year_match = _YEAR_RE.search(stem) or _YEAR_RE.search(
        " ".join(pages[:2])[:4000] if pages else ""
    )
    if year_match:
        year = int(year_match.group(0))

    if title is None:
        # First non-trivial line of page 1 is usually the paper title.
        for line in (pages[0] if pages else "").splitlines():
            candidate = line.strip()
            if 20 <= len(candidate) <= 300:
                title = candidate
                break
    if title is None:
        title = stem.replace("_", " ").replace("-", " ").strip() or filename

    key_base = None
    if author:
        surname = _KEY_SANITIZE_RE.sub("", author.split(",")[0].split()[-1])
        if surname:
            key_base = surname[:40].capitalize()
    if key_base is None:
        first_token = _KEY_SANITIZE_RE.sub("", stem.split("_")[0].split()[0])
        key_base = (first_token[:40] or "Fonte").capitalize()
    citation_key = f"{key_base}{year}" if year else key_base

    return {
        "citation_key": citation_key,
        "title": title,
        "authors": author,
        "year": year,
        "metadata_incomplete": author is None or year is None,
    }


def split_passages(
    *,
    source_file_id: int,
    citation_key: str,
    filename: str,
    pages: list[tuple[int, str]],
) -> list[SourcePassage]:
    """Page-bounded windows: a passage never spans pages, so its page
    number is exact evidence, not an approximation."""
    passages: list[SourcePassage] = []
    for page_number, text in pages:
        blocks = [b.strip() for b in re.split(r"\n\s*\n", text) if b.strip()]
        if not blocks and text.strip():
            blocks = [text.strip()]
        window = ""
        for block in blocks:
            candidate = f"{window}\n{block}".strip() if window else block
            if len(candidate) <= PASSAGE_TARGET_CHARS:
                window = candidate
                continue
            if len(window) >= PASSAGE_MIN_CHARS:
                passages.append(
                    SourcePassage(
                        source_file_id=source_file_id,
                        citation_key=citation_key,
                        filename=filename,
                        page_number=page_number,
                        text=window,
                    )
                )
            window = block[:PASSAGE_TARGET_CHARS]
        if len(window) >= PASSAGE_MIN_CHARS:
            passages.append(
                SourcePassage(
                    source_file_id=source_file_id,
                    citation_key=citation_key,
                    filename=filename,
                    page_number=page_number,
                    text=window,
                )
            )
    return passages


def score_passage(query: str, passage_text: str) -> float:
    """Lexical overlap score in [0, 1]-ish: coverage of query terms with a
    small density bonus. Language-tolerant via accent stripping; no model
    calls, so retrieval is deterministic and testable."""
    query_terms = set(_terms(query))
    if not query_terms:
        return 0.0
    passage_terms = _terms(passage_text)
    if not passage_terms:
        return 0.0
    passage_set = set(passage_terms)
    covered = sum(1 for t in query_terms if t in passage_set)
    coverage = covered / len(query_terms)
    density = sum(1 for t in passage_terms if t in query_terms) / len(passage_terms)
    return round(coverage + min(density, 0.2), 4)


def select_passages(
    passages: list[SourcePassage], query: str, *, limit: int = 6
) -> list[SourcePassage]:
    """Top passages for a query, at most two per file so one source cannot
    monopolize the prompt."""
    scored = sorted(
        (
            SourcePassage(
                source_file_id=p.source_file_id,
                citation_key=p.citation_key,
                filename=p.filename,
                page_number=p.page_number,
                text=p.text,
                score=score_passage(query, p.text),
            )
            for p in passages
        ),
        key=lambda p: (-p.score, p.citation_key, p.page_number),
    )
    selected: list[SourcePassage] = []
    per_file: dict[int, int] = {}
    for passage in scored:
        if passage.score <= 0:
            break
        if per_file.get(passage.source_file_id, 0) >= 2:
            continue
        selected.append(passage)
        per_file[passage.source_file_id] = per_file.get(passage.source_file_id, 0) + 1
        if len(selected) >= limit:
            break
    return selected


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


async def load_document_passages(
    db: AsyncSession, document_id: int
) -> list[SourcePassage]:
    """All retrievable passages of a document's parsed uploaded sources."""
    files = (
        (
            await db.execute(
                select(DocumentSourceFile).where(
                    DocumentSourceFile.document_id == document_id,
                    DocumentSourceFile.status == "parsed",
                )
            )
        )
        .scalars()
        .all()
    )
    if not files:
        return []
    passages: list[SourcePassage] = []
    for source_file in files:
        rows = (
            (
                await db.execute(
                    select(SourceFilePage)
                    .where(SourceFilePage.source_file_id == source_file.id)
                    .order_by(SourceFilePage.page_number.asc())
                )
            )
            .scalars()
            .all()
        )
        passages.extend(
            split_passages(
                source_file_id=int(source_file.id),
                citation_key=str(source_file.citation_key),
                filename=str(source_file.filename),
                pages=[(int(r.page_number), str(r.text)) for r in rows],
            )
        )
    return passages


async def uploaded_sources_digest(db: AsyncSession, document_id: int) -> str | None:
    """Deterministic digest of the uploaded source set, for the generation
    contract: swapping sources after enqueue must invalidate the run just
    like swapping the methodology does."""
    hashes = (
        (
            await db.execute(
                select(DocumentSourceFile.sha256)
                .where(DocumentSourceFile.document_id == document_id)
                .order_by(DocumentSourceFile.sha256.asc())
            )
        )
        .scalars()
        .all()
    )
    if not hashes:
        return None
    return hashlib.sha256("\n".join(hashes).encode("utf-8")).hexdigest()


async def build_uploaded_source_pack(db: AsyncSession, document_id: int, topic: str):
    """Build the grounding pack FROM manager-uploaded PDFs, or None.

    When uploads exist they replace API retrieval entirely: the manager
    chose these readings, so every file enters the pack with
    on_topic_score 1.0 (the score exists to filter API junk, not to
    second-guess a mandated bibliography). Deterministic — a resumed run
    rebuilds the identical pack, passages included.

    Formatting fallbacks are honest but visible: files without extractable
    authors/year get filename-derived authors and the upload year so the
    [Key] -> (Author, Year) conversion can never leak internal markers into
    the delivered text; such files stay flagged metadata_incomplete for the
    manager to correct before release.
    """
    from app.services.ai_pipeline.rag_retriever import SourceDoc
    from app.services.ai_pipeline.source_pack import PackedSource, SourcePack

    files = (
        (
            await db.execute(
                select(DocumentSourceFile)
                .where(
                    DocumentSourceFile.document_id == document_id,
                    DocumentSourceFile.status == "parsed",
                )
                .order_by(DocumentSourceFile.id.asc())
            )
        )
        .scalars()
        .all()
    )
    if not files:
        return None

    all_passages: list[SourcePassage] = []
    packed: list[PackedSource] = []
    for source_file in files:
        rows = (
            (
                await db.execute(
                    select(SourceFilePage)
                    .where(SourceFilePage.source_file_id == source_file.id)
                    .order_by(SourceFilePage.page_number.asc())
                )
            )
            .scalars()
            .all()
        )
        passages = split_passages(
            source_file_id=int(source_file.id),
            citation_key=str(source_file.citation_key),
            filename=str(source_file.filename),
            pages=[(int(r.page_number), str(r.text)) for r in rows],
        )
        all_passages.extend(passages)

        authors = [
            a.strip() for a in str(source_file.authors or "").split(";") if a.strip()
        ]
        if not authors:
            stem = re.sub(r"\.pdf$", "", str(source_file.filename), flags=re.I)
            authors = [stem.replace("_", " ").split()[0][:60] or "Fonte"]
        year = (
            int(source_file.year)
            if source_file.year
            else (
                source_file.created_at.year
                if source_file.created_at is not None
                else 2026
            )
        )
        abstract = passages[0].text[:1000] if passages else None
        packed.append(
            PackedSource(
                SourceDoc(
                    title=str(source_file.title or source_file.filename),
                    authors=authors,
                    year=year,
                    abstract=abstract,
                    paper_id=f"uploaded:{int(source_file.id)}",
                    venue=None,
                    url=None,
                    doi=None,
                ),
                str(source_file.citation_key),
                1.0,
            )
        )

    pack = SourcePack(document_id=document_id, topic=topic, sources=packed)
    pack.passages = all_passages
    logger.info(
        "Built uploaded-sources pack for document %s: %s files, %s passages",
        document_id,
        len(packed),
        len(all_passages),
    )
    return pack
