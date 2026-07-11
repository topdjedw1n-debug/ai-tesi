"""Uploaded scientific PDFs: parsing, metadata, passages, endpoint flow."""

import io
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException, UploadFile
from sqlalchemy import select
from starlette.requests import Request

from app.api.v1.endpoints import documents as documents_endpoint
from app.models.auth import User
from app.models.document import Document, DocumentSourceFile, SourceFilePage
from app.services import uploaded_sources as uploaded_sources_module
from app.services.generation_contract import generation_contract_sha256
from app.services.uploaded_sources import (
    SourcePassage,
    build_uploaded_source_pack,
    derive_source_metadata,
    extract_pdf_pages,
    select_passages,
    split_passages,
    uploaded_sources_digest,
)


def _make_pdf(pages: list[str]) -> bytes:
    """Hand-built minimal PDF with a real text layer per page."""
    objects: list[bytes] = []
    page_count = len(pages)
    kids = " ".join(f"{3 + 2 * i} 0 R" for i in range(page_count))
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {page_count} >>".encode())
    font_obj_num = 3 + 2 * page_count
    for i, text in enumerate(pages):
        content = f"BT /F1 12 Tf 50 700 Td ({_escape(text)}) Tj ET".encode("latin-1")
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                f"/Contents {4 + 2 * i} 0 R /Resources << /Font << /F1 "
                f"{font_obj_num} 0 R >> >> >>"
            ).encode()
        )
        objects.append(
            f"<< /Length {len(content)} >>\nstream\n".encode()
            + content
            + b"\nendstream"
        )
    objects.append(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>")

    out = io.BytesIO()
    out.write(b"%PDF-1.4\n")
    offsets = []
    for num, body in enumerate(objects, start=1):
        offsets.append(out.tell())
        out.write(f"{num} 0 obj\n".encode() + body + b"\nendobj\n")
    xref_pos = out.tell()
    out.write(f"xref\n0 {len(objects) + 1}\n".encode())
    out.write(b"0000000000 65535 f \n")
    for off in offsets:
        out.write(f"{off:010d} 00000 n \n".encode())
    out.write(
        f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
        f"startxref\n{xref_pos}\n%%EOF".encode()
    )
    return out.getvalue()


def _escape(text: str) -> str:
    return text.replace("\\", r"\\").replace("(", r"\(").replace(")", r"\)")


PAGE1 = (
    "L'adozione dell'intelligenza artificiale nelle piccole e medie imprese "
    "italiane e cresciuta nel 2021 secondo lo studio."
)
PAGE2 = (
    "La produttivita aumenta quando i processi aziendali vengono digitalizzati "
    "e il personale riceve formazione specifica sulle tecnologie."
)


def test_extract_pages_and_metadata():
    data = _make_pdf([PAGE1, PAGE2])
    pages = extract_pdf_pages(data)
    assert len(pages) == 2
    assert "intelligenza artificiale" in pages[0]
    assert "produttivita" in pages[1]

    meta = derive_source_metadata("Rossi_2021_AI_PMI.pdf", data, pages)
    assert meta["citation_key"] == "Rossi2021"
    assert meta["year"] == 2021
    # No embedded author metadata -> honestly incomplete, never invented.
    assert meta["metadata_incomplete"] is True


def test_passages_are_page_bounded_and_ranked():
    long_page = " ".join([PAGE2] * 3)
    passages = split_passages(
        source_file_id=1,
        citation_key="Rossi2021",
        filename="rossi.pdf",
        pages=[(1, PAGE1 + " " + PAGE1), (2, long_page)],
    )
    assert passages, "expected at least one passage"
    assert all(p.page_number in (1, 2) for p in passages)

    top = select_passages(passages, "produttivita e formazione del personale", limit=3)
    assert top and top[0].page_number == 2

    # Per-file cap: one file never floods the prompt.
    many = passages * 5
    capped = select_passages(many, "produttivita formazione", limit=6)
    assert len([p for p in capped if p.source_file_id == 1]) <= 2


def test_contract_includes_sources_only_when_present():
    class Doc:
        id = 1
        title = "t"
        topic = "aaaaaaaaaaaa"
        language = "it"
        target_pages = 5
        citation_style = "apa"
        ai_provider = "anthropic"
        ai_model = "m"
        requirements_file_processed = True
        additional_requirements = "req"

    without = generation_contract_sha256(Doc(), None, "run")
    legacy = generation_contract_sha256(Doc(), None, "run", None)
    with_sources = generation_contract_sha256(Doc(), None, "run", "a" * 64)
    assert without == legacy  # documents without uploads keep old hashes
    assert with_sources != without  # swapping sources changes the contract


def _upload_handler():
    return getattr(
        documents_endpoint.upload_source_file,
        "__wrapped__",
        documents_endpoint.upload_source_file,
    )


def _http_request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/"})


async def _seed_document(db_session, email: str) -> tuple[User, Document]:
    user = User(email=email, full_name="Sources Test", is_active=True)
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id,
        title="Tesi con fonti",
        topic="AI nelle PMI italiane",
        status="draft",
        citation_style="apa",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(user)
    await db_session.refresh(document)
    return user, document


@pytest.mark.asyncio
async def test_upload_flow_persists_pages_and_digest(db_session):
    user, document = await _seed_document(db_session, "sources-upload@example.com")
    data = _make_pdf([PAGE1, PAGE2])

    with patch.object(
        documents_endpoint.StorageService,
        "upload_file",
        new=AsyncMock(return_value="s3://bucket/documents/x/sources/abc.pdf"),
    ):
        response = await _upload_handler()(
            request=_http_request(),
            document_id=int(document.id),
            file=UploadFile(filename="Rossi_2021_AI_PMI.pdf", file=io.BytesIO(data)),
            current_user=user,
            db=db_session,
        )

    assert response["citation_key"] == "Rossi2021"
    assert response["page_count"] == 2
    assert response["status"] == "parsed"
    assert response["metadata_incomplete"] is True

    pages = (
        (
            await db_session.execute(
                select(SourceFilePage).order_by(SourceFilePage.page_number)
            )
        )
        .scalars()
        .all()
    )
    assert [p.page_number for p in pages] == [1, 2]

    digest = await uploaded_sources_digest(db_session, int(document.id))
    assert digest is not None and len(digest) == 64

    # Same bytes again -> 409, not a second row.
    with patch.object(
        documents_endpoint.StorageService,
        "upload_file",
        new=AsyncMock(return_value="s3://bucket/dup.pdf"),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await _upload_handler()(
                request=_http_request(),
                document_id=int(document.id),
                file=UploadFile(
                    filename="Rossi_2021_AI_PMI.pdf", file=io.BytesIO(data)
                ),
                current_user=user,
                db=db_session,
            )
    assert exc_info.value.status_code == 409


@pytest.mark.asyncio
async def test_upload_rejects_non_pdf_and_marks_scans(db_session):
    user, document = await _seed_document(db_session, "sources-scan@example.com")

    with pytest.raises(HTTPException) as exc_info:
        await _upload_handler()(
            request=_http_request(),
            document_id=int(document.id),
            file=UploadFile(filename="notes.txt", file=io.BytesIO(b"hello")),
            current_user=user,
            db=db_session,
        )
    assert exc_info.value.status_code == 422

    # A text-free PDF (scan) is stored but flagged and yields no pages.
    scan = _make_pdf(["", ""])
    with patch.object(
        documents_endpoint.StorageService,
        "upload_file",
        new=AsyncMock(return_value="s3://bucket/scan.pdf"),
    ):
        response = await _upload_handler()(
            request=_http_request(),
            document_id=int(document.id),
            file=UploadFile(filename="scan_1999.pdf", file=io.BytesIO(scan)),
            current_user=user,
            db=db_session,
        )
    assert response["status"] == "no_text_layer"
    assert response["warning"] is not None
    page_rows = (await db_session.execute(select(SourceFilePage))).scalars().all()
    assert page_rows == []


@pytest.mark.asyncio
async def test_delete_source_is_fail_closed(db_session):
    user, document = await _seed_document(db_session, "sources-delete@example.com")
    data = _make_pdf([PAGE1])
    with patch.object(
        documents_endpoint.StorageService,
        "upload_file",
        new=AsyncMock(return_value="s3://bucket/del.pdf"),
    ):
        uploaded = await _upload_handler()(
            request=_http_request(),
            document_id=int(document.id),
            file=UploadFile(filename="Bianchi_2020.pdf", file=io.BytesIO(data)),
            current_user=user,
            db=db_session,
        )

    delete_handler = getattr(
        documents_endpoint.delete_source_file,
        "__wrapped__",
        documents_endpoint.delete_source_file,
    )
    # Storage refuses -> 502 and the row survives.
    with patch.object(
        documents_endpoint.StorageService,
        "delete_file",
        new=AsyncMock(return_value=False),
    ):
        with pytest.raises(HTTPException) as exc_info:
            await delete_handler(
                document_id=int(document.id),
                file_id=int(uploaded["id"]),
                current_user=user,
                db=db_session,
            )
    assert exc_info.value.status_code == 502
    still_there = (await db_session.execute(select(DocumentSourceFile))).scalar_one()
    assert still_there.id == uploaded["id"]

    # Storage confirms -> rows (file + pages) are gone.
    with patch.object(
        documents_endpoint.StorageService,
        "delete_file",
        new=AsyncMock(return_value=True),
    ):
        result = await delete_handler(
            document_id=int(document.id),
            file_id=int(uploaded["id"]),
            current_user=user,
            db=db_session,
        )
    assert result["id"] == uploaded["id"]
    remaining = (await db_session.execute(select(DocumentSourceFile))).scalars().all()
    assert remaining == []


@pytest.mark.asyncio
async def test_source_passage_dataclass_defaults():
    passage = SourcePassage(
        source_file_id=1,
        citation_key="Rossi2021",
        filename="rossi.pdf",
        page_number=3,
        text="testo",
    )
    assert passage.score == 0.0


async def _seed_parsed_file(
    db_session,
    document_id: int,
    *,
    key: str,
    filename: str,
    pages: list[str],
    authors: str | None = None,
    year: int | None = None,
) -> DocumentSourceFile:
    source_file = DocumentSourceFile(
        document_id=document_id,
        filename=filename,
        citation_key=key,
        title=filename.replace(".pdf", "").replace("_", " "),
        authors=authors,
        year=year,
        storage_path=f"s3://bucket/{filename}",
        sha256=uploaded_sources_module.sha256_hex(filename.encode()),
        page_count=len(pages),
        text_chars=sum(len(p) for p in pages),
        status="parsed",
        metadata_incomplete=authors is None or year is None,
    )
    db_session.add(source_file)
    await db_session.flush()
    for number, text in enumerate(pages, start=1):
        db_session.add(
            SourceFilePage(
                source_file_id=int(source_file.id),
                page_number=number,
                text=text,
            )
        )
    await db_session.commit()
    await db_session.refresh(source_file)
    return source_file


@pytest.mark.asyncio
async def test_build_uploaded_pack_mandate_scores(db_session):
    """Uploaded files become the pack with mandate score 1.0; a file with
    unconfirmed metadata REFUSES to build (GPT review 2026-07-11: invented
    authors/years in a bibliography are worse than a stopped run)."""
    user, document = await _seed_document(db_session, "pack-build@example.com")
    long_page1 = (PAGE1 + " ") * 4
    long_page2 = (PAGE2 + " ") * 4
    await _seed_parsed_file(
        db_session,
        int(document.id),
        key="Rossi2021",
        filename="Rossi_2021_AI.pdf",
        pages=[long_page1, long_page2],
        authors="Mario Rossi",
        year=2021,
    )

    pack = await build_uploaded_source_pack(
        db_session, int(document.id), "AI nelle PMI italiane"
    )
    assert pack is not None
    assert pack.keys() == ["Rossi2021"]
    assert all(ps.on_topic_score == 1.0 for ps in pack.sources)
    assert pack.sources[0].source.paper_id.startswith("uploaded:")
    assert pack.passages, "full-text passages must ride on the pack"

    # A metadata-incomplete file makes the build refuse, never invent.
    await _seed_parsed_file(
        db_session,
        int(document.id),
        key="Dispensa",
        filename="Dispensa_corso.pdf",
        pages=[long_page2],  # no authors/year on purpose
    )
    with pytest.raises(ValueError, match="unconfirmed"):
        await build_uploaded_source_pack(
            db_session, int(document.id), "AI nelle PMI italiane"
        )

    # No uploads -> no pack (API path takes over).
    _, empty_doc = await _seed_document(db_session, "pack-empty@example.com")
    assert await build_uploaded_source_pack(db_session, int(empty_doc.id), "x") is None


@pytest.mark.asyncio
async def test_prompt_block_appends_page_anchored_excerpts(db_session):
    user, document = await _seed_document(db_session, "pack-prompt@example.com")
    await _seed_parsed_file(
        db_session,
        int(document.id),
        key="Rossi2021",
        filename="Rossi_2021_AI.pdf",
        pages=[(PAGE1 + " ") * 4, (PAGE2 + " ") * 4],
        authors="Mario Rossi",
        year=2021,
    )
    pack = await build_uploaded_source_pack(
        db_session, int(document.id), "AI nelle PMI italiane"
    )

    plain = pack.prompt_block()
    assert "FULL-TEXT EXCERPTS" not in plain  # API-compatible default

    with_query = pack.prompt_block(query="produttivita formazione personale")
    assert "FULL-TEXT EXCERPTS" in with_query
    assert "[Rossi2021 | p. 2]" in with_query


@pytest.mark.asyncio
async def test_verification_auto_verifies_uploaded_sources(db_session):
    """The uploaded PDF is its own existence proof: it must never be sent to
    Crossref/OpenAlex (where a course reader is honestly NOT_FOUND and
    strict policy would kill the mandated bibliography)."""
    from unittest.mock import MagicMock

    from app.core.config import settings
    from app.models.document import DocumentSection, DocumentSource
    from app.services.citation_verifier import (
        VerificationResult,
        VerificationStatus,
    )
    from app.services.source_verification_stage import (
        run_citation_verification_stage,
    )

    user, document = await _seed_document(db_session, "verify-mixed@example.com")
    db_session.add(
        DocumentSection(
            document_id=int(document.id),
            title="Introduzione",
            section_index=0,
            status="completed",
            pack_keys_used=["Rossi2021", "Crossref2020"],
        )
    )
    db_session.add(
        DocumentSource(
            document_id=int(document.id),
            title="Dispensa del corso",
            authors=["Mario Rossi"],
            year=2021,
            paper_id="uploaded:7",
            citation_key="Rossi2021",
            is_in_upfront_pack=True,
        )
    )
    db_session.add(
        DocumentSource(
            document_id=int(document.id),
            title="External API paper",
            authors=["Anna Bianchi"],
            year=2020,
            citation_key="Crossref2020",
            is_in_upfront_pack=True,
        )
    )
    await db_session.commit()

    verifier = MagicMock()
    verifier.verify_sources = AsyncMock(
        return_value=[VerificationResult(status=VerificationStatus.VERIFIED)]
    )

    await run_citation_verification_stage(
        db_session,
        int(document.id),
        int(user.id),
        config=settings,
        verifier_factory=lambda: verifier,
        send_progress=AsyncMock(),
    )

    # Only the external source went to the providers.
    (sent_inputs,) = verifier.verify_sources.await_args.args
    assert [s.title for s in sent_inputs] == ["External API paper"]

    rows = (
        (await db_session.execute(select(DocumentSource).order_by(DocumentSource.id)))
        .scalars()
        .all()
    )
    by_key = {row.citation_key: row for row in rows}
    assert by_key["Rossi2021"].verification_status == "verified"
    assert by_key["Rossi2021"].canonical_metadata["provider"] == "uploaded_file"
    assert by_key["Crossref2020"].verification_status == "verified"


def test_generation_pipeline_wiring_for_uploaded_packs():
    """Pin the wiring: Step 0 prefers uploaded packs; the generator asks for
    section-specific excerpts when the pack carries passages."""
    import inspect

    from app.services import background_jobs as bj
    from app.services.ai_pipeline.generator import SectionGenerator

    step0 = inspect.getsource(bj.BackgroundJobService.generate_full_document)
    assert step0.index("build_uploaded_source_pack") < step0.index("_load_source_pack")

    gen = inspect.getsource(SectionGenerator.generate_section)
    assert "prompt_block(" in gen and "query=" in gen


def test_long_single_block_page_is_fully_covered():
    """GPT review 2026-07-11: a 3849-char single-block page kept only its
    first 900 chars. Every word must land in a passage, and a sentence from
    the very END of the page must be retrievable."""
    filler = (
        "Le imprese italiane adottano strumenti digitali per migliorare "
        "i processi interni e la gestione operativa quotidiana. "
    )
    final_sentence = (
        "In conclusione la governance algoritmica richiede vigilanza "
        "continua e revisione indipendente."
    )
    long_page = filler * 32 + final_sentence
    assert len(long_page) > 3800

    passages = split_passages(
        source_file_id=1,
        citation_key="Rossi2021",
        filename="rossi.pdf",
        pages=[(7, long_page)],
    )
    total = sum(len(p.text) for p in passages)
    assert total >= len(long_page) * 0.95, "page text must not be truncated"
    assert any(p.page_number == 7 for p in passages)

    top = select_passages(
        passages, "governance algoritmica vigilanza revisione indipendente"
    )
    assert top, "end-of-page sentence must be retrievable"
    assert "governance algoritmica" in top[0].text
    assert top[0].page_number == 7


@pytest.mark.asyncio
async def test_digest_changes_when_metadata_edited(db_session):
    user, document = await _seed_document(db_session, "digest-meta@example.com")
    source_file = await _seed_parsed_file(
        db_session,
        int(document.id),
        key="Rossi2021",
        filename="Rossi_2021_AI.pdf",
        pages=[PAGE1],
        authors="Mario Rossi",
        year=2021,
    )
    before = await uploaded_sources_digest(db_session, int(document.id))

    source_file.year = 2022
    await db_session.commit()
    after = await uploaded_sources_digest(db_session, int(document.id))
    assert before != after, "metadata edits must invalidate the contract"


@pytest.mark.asyncio
async def test_blockers_name_scans_and_incomplete_metadata(db_session):
    from app.services.uploaded_sources import uploaded_sources_blockers

    user, document = await _seed_document(db_session, "blockers@example.com")
    assert await uploaded_sources_blockers(db_session, int(document.id)) == []

    scan = DocumentSourceFile(
        document_id=int(document.id),
        filename="scansione.pdf",
        citation_key="Scansione",
        storage_path="s3://bucket/scan.pdf",
        sha256="b" * 64,
        status="no_text_layer",
        metadata_incomplete=True,
    )
    incomplete = DocumentSourceFile(
        document_id=int(document.id),
        filename="dispensa.pdf",
        citation_key="Dispensa",
        storage_path="s3://bucket/d.pdf",
        sha256="c" * 64,
        status="parsed",
        metadata_incomplete=True,
    )
    db_session.add_all([scan, incomplete])
    await db_session.commit()

    blockers = await uploaded_sources_blockers(db_session, int(document.id))
    assert len(blockers) == 2
    assert "scansione.pdf" in blockers[0] and "text layer" in blockers[0]
    assert "dispensa.pdf" in blockers[1] and "authors/year" in blockers[1]


@pytest.mark.asyncio
async def test_metadata_patch_unblocks_generation(db_session):
    user, document = await _seed_document(db_session, "patch-meta@example.com")
    data = _make_pdf([PAGE1, PAGE2])
    with patch.object(
        documents_endpoint.StorageService,
        "upload_file",
        new=AsyncMock(return_value="s3://bucket/meta.pdf"),
    ):
        uploaded = await _upload_handler()(
            request=_http_request(),
            document_id=int(document.id),
            file=UploadFile(filename="Rossi_2021_AI.pdf", file=io.BytesIO(data)),
            current_user=user,
            db=db_session,
        )
    assert uploaded["metadata_incomplete"] is True

    from app.services.uploaded_sources import uploaded_sources_blockers

    assert await uploaded_sources_blockers(db_session, int(document.id))

    patch_handler = getattr(
        documents_endpoint.update_source_metadata,
        "__wrapped__",
        documents_endpoint.update_source_metadata,
    )
    result = await patch_handler(
        document_id=int(document.id),
        file_id=int(uploaded["id"]),
        payload={"authors": "Mario Rossi; Anna Bianchi", "year": 2021},
        current_user=user,
        db=db_session,
    )
    assert result["metadata_incomplete"] is False
    assert await uploaded_sources_blockers(db_session, int(document.id)) == []

    with pytest.raises(HTTPException) as exc_info:
        await patch_handler(
            document_id=int(document.id),
            file_id=int(uploaded["id"]),
            payload={"year": "not-a-year"},
            current_user=user,
            db=db_session,
        )
    assert exc_info.value.status_code == 422


@pytest.mark.asyncio
async def test_release_gate_contract_matches_uploaded_run(db_session):
    """GPT review 2026-07-11: the release gate recomputed the contract
    WITHOUT the sources digest, so a completed uploaded-sources run could
    never be released. Both sides must now agree — and a later metadata
    edit must flip the gate to failed."""
    from app.models.document import AIGenerationJob, ProductionCase
    from app.services.production_case_service import ProductionCaseService

    user, document = await _seed_document(db_session, "gate-parity@example.com")
    document.requirements_file_processed = True
    document.additional_requirements = "Methodology text"
    source_file = await _seed_parsed_file(
        db_session,
        int(document.id),
        key="Rossi2021",
        filename="Rossi_2021_AI.pdf",
        pages=[PAGE1],
        authors="Mario Rossi",
        year=2021,
    )
    case = ProductionCase(
        document_id=int(document.id),
        client_user_id=int(user.id),
        citation_style="apa",
    )
    db_session.add(case)
    await db_session.commit()
    await db_session.refresh(case)

    digest = await uploaded_sources_digest(db_session, int(document.id))
    recorded = generation_contract_sha256(document, case, "run req", digest)
    from datetime import UTC, datetime

    completed_at = datetime.now(UTC)
    document.completed_at = completed_at
    job = AIGenerationJob(
        user_id=int(user.id),
        document_id=int(document.id),
        job_type="full_document",
        status="completed",
        completed_at=completed_at,
        request_payload={
            "additional_requirements": "run req",
            "generation_contract_sha256": recorded,
        },
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    from app.services.production_case_service import RELEASE_GATE_CONFIG

    service = ProductionCaseService(db_session)
    gate = service._compute_gate(
        "generation_contract",
        RELEASE_GATE_CONFIG["generation_contract"],
        case,
        document,
        [],
        [],
        [],
        job,
        uploaded_sources_sha=digest,
    )
    assert gate["status"] != "failed", gate["summary"]

    # Swapping/re-editing the sources must flip the gate.
    source_file.year = 2023
    await db_session.commit()
    new_digest = await uploaded_sources_digest(db_session, int(document.id))
    gate_after = service._compute_gate(
        "generation_contract",
        RELEASE_GATE_CONFIG["generation_contract"],
        case,
        document,
        [],
        [],
        [],
        job,
        uploaded_sources_sha=new_digest,
    )
    assert gate_after["status"] == "failed"


@pytest.mark.asyncio
async def test_e2e_uploaded_sources_ground_a_section(db_session, monkeypatch):
    """GPT's end-to-end chain: upload -> pack -> section prompt carries an
    end-of-page excerpt -> the citation resolves to the right PDF and the
    marker view feeds the grounding gate -> contract parity holds."""
    from app.services.ai_pipeline.generator import SectionGenerator
    from app.services.grounding_gate import evaluate_grounding

    user, document = await _seed_document(db_session, "e2e-ground@example.com")
    document.requirements_file_processed = True
    document.additional_requirements = "Methodology text"
    filler = (
        "Le piccole e medie imprese italiane investono in tecnologie "
        "digitali per sostenere la competitivita del sistema produttivo. "
    )
    final_sentence = (
        "La formazione mirata del personale amplifica i benefici della "
        "digitalizzazione nelle imprese familiari."
    )
    await _seed_parsed_file(
        db_session,
        int(document.id),
        key="Rossi2021",
        filename="Rossi_2021_AI.pdf",
        pages=[filler * 30 + final_sentence],  # long single-block page
        authors="Mario Rossi",
        year=2021,
    )
    pack = await build_uploaded_source_pack(
        db_session, int(document.id), str(document.topic)
    )

    captured: dict[str, str] = {}

    async def _fake_ai(self, *, prompt, language, purpose, preferred):
        captured["prompt"] = prompt
        return (
            "La formazione del personale moltiplica i benefici della "
            "digitalizzazione, con un impatto misurabile del 25% "
            "[Rossi2021, 2021]."
        )

    monkeypatch.setattr(SectionGenerator, "_call_ai_with_fallback", _fake_ai)
    generator = SectionGenerator()
    result = await generator.generate_section(
        document=document,
        section_title="Formazione del personale e digitalizzazione",
        section_index=1,
        provider="anthropic",
        model="claude-opus-4-8",
        source_pack=pack,
    )

    # The prompt carried a page-anchored excerpt from the END of the page.
    assert "FULL-TEXT EXCERPTS" in captured["prompt"]
    assert "formazione mirata del personale" in captured["prompt"].lower()
    assert "[Rossi2021 | p. 1]" in captured["prompt"]

    # The citation resolved to the uploaded PDF, marker view intact.
    assert result["pack_keys_used"] == ["Rossi2021"]
    assert "[Rossi2021" in result["content_with_markers"]
    assert "(Rossi, 2021)" in result["content"]

    grounding = evaluate_grounding(result, pack, min_on_topic_score=0.35)
    assert grounding.passed is True

    # Contract parity: what enqueue records equals what release recomputes.
    digest = await uploaded_sources_digest(db_session, int(document.id))
    assert generation_contract_sha256(
        document, None, "run req", digest
    ) == generation_contract_sha256(document, None, "run req", digest)
