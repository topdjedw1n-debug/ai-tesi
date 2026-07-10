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
from app.services.generation_contract import generation_contract_sha256
from app.services.uploaded_sources import (
    SourcePassage,
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
