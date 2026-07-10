"""Regression tests for persisted uploaded university requirements."""

import io
from unittest.mock import MagicMock

import pytest
from fastapi import HTTPException, UploadFile, status
from starlette.datastructures import Headers

from app.api.v1.endpoints.documents import upload_custom_requirements
from app.models.auth import User
from app.models.document import AIGenerationJob, Document, ProductionCase
from app.services.custom_requirements_service import MAX_STORED_REQUIREMENTS_CHARS
from app.services.generation_contract import generation_contract_sha256
from app.services.generation_worker import claim_next_generation_job, utc_now


def _text_upload(text: str) -> UploadFile:
    payload = text.encode("utf-8")
    return UploadFile(
        file=io.BytesIO(payload),
        size=len(payload),
        filename="university-methodology.txt",
        headers=Headers({"content-type": "text/plain"}),
    )


@pytest.mark.asyncio
async def test_uploaded_methodology_is_appended_and_persisted(db_session):
    """Uploaded text must survive the request and preserve intake requirements."""
    user = User(email="methodology-owner@example.com", full_name="Methodology Owner")
    db_session.add(user)
    await db_session.flush()

    intake_requirements = "Citation style: Chicago. Work type: Master's thesis."
    document = Document(
        user_id=user.id,
        title="Italian Thesis",
        topic="Digital transformation in Italian universities",
        additional_requirements=intake_requirements,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    document_id = document.id

    methodology_text = (
        "La tesi deve includere introduzione, capitoli numerati e conclusioni."
    )
    response = await upload_custom_requirements(
        request=MagicMock(),
        document_id=document_id,
        file=_text_upload(methodology_text),
        current_user=user,
        db=db_session,
    )

    db_session.expire_all()
    persisted = await db_session.get(Document, document_id)

    assert persisted is not None
    assert persisted.additional_requirements is not None
    assert persisted.additional_requirements.startswith(intake_requirements)
    assert "UPLOADED UNIVERSITY REQUIREMENTS" in persisted.additional_requirements
    assert methodology_text in persisted.additional_requirements
    assert persisted.requirements_file_processed is True
    assert response["file_size"] == len(methodology_text)


@pytest.mark.asyncio
async def test_worker_accepts_contract_created_by_real_methodology_upload(db_session):
    user = User(email="methodology-worker-contract@example.com")
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id,
        title="UNIBO Thesis",
        topic="Digital governance in Italian universities",
        citation_style="apa",
    )
    db_session.add(document)
    await db_session.commit()

    await upload_custom_requirements(
        request=MagicMock(),
        document_id=document.id,
        file=_text_upload("Linee guida ufficiali UNIBO per la tesi magistrale."),
        current_user=user,
        db=db_session,
    )
    await db_session.refresh(document)
    document.status = "generating"
    job = AIGenerationJob(
        user_id=user.id,
        document_id=document.id,
        job_type="full_document",
        status="queued",
        request_payload={
            "additional_requirements": None,
            "generation_contract_sha256": generation_contract_sha256(
                document, None, None
            ),
        },
    )
    db_session.add(job)
    await db_session.commit()

    claimed = await claim_next_generation_job(
        db_session, worker_id="methodology-contract-worker", now=utc_now()
    )
    assert claimed is not None
    assert claimed.id == job.id


@pytest.mark.asyncio
async def test_oversized_combined_requirements_are_rejected_without_truncation(
    db_session,
):
    """The API must reject excessive prompt context, not save a partial methodic."""
    user = User(email="methodology-limit@example.com", full_name="Limit Owner")
    db_session.add(user)
    await db_session.flush()

    intake_requirements = "Keep these original intake requirements."
    document = Document(
        user_id=user.id,
        title="Italian Thesis",
        topic="Governance of digital public services in Italy",
        additional_requirements=intake_requirements,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    document_id = document.id

    with pytest.raises(HTTPException) as exc_info:
        await upload_custom_requirements(
            request=MagicMock(),
            document_id=document_id,
            file=_text_upload("x" * MAX_STORED_REQUIREMENTS_CHARS),
            current_user=user,
            db=db_session,
        )

    assert exc_info.value.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert f"{MAX_STORED_REQUIREMENTS_CHARS}-character limit" in exc_info.value.detail

    db_session.expire_all()
    persisted = await db_session.get(Document, document_id)
    assert persisted is not None
    assert persisted.additional_requirements == intake_requirements


@pytest.mark.asyncio
async def test_non_owner_cannot_replace_uploaded_requirements(db_session):
    """Ownership must be checked before uploaded content is extracted or stored."""
    owner = User(email="methodology-real-owner@example.com")
    other_user = User(email="methodology-other-user@example.com")
    db_session.add_all([owner, other_user])
    await db_session.flush()

    original_requirements = "Original owner's requirements."
    document = Document(
        user_id=owner.id,
        title="Protected Thesis",
        topic="Privacy safeguards in Italian universities",
        additional_requirements=original_requirements,
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    document_id = document.id

    with pytest.raises(HTTPException) as exc_info:
        await upload_custom_requirements(
            request=MagicMock(),
            document_id=document_id,
            file=_text_upload("Attacker supplied requirements."),
            current_user=other_user,
            db=db_session,
        )

    assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    db_session.expire_all()
    persisted = await db_session.get(Document, document_id)
    assert persisted is not None
    assert persisted.additional_requirements == original_requirements


@pytest.mark.asyncio
async def test_methodology_change_revokes_previous_release(db_session):
    user = User(email="released-methodology-owner@example.com")
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id,
        title="Released Thesis",
        topic="Digital transformation in Italian public administration",
        status="completed",
        docx_path="exports/released.docx",
    )
    db_session.add(document)
    await db_session.flush()
    case = ProductionCase(
        document_id=document.id,
        client_user_id=user.id,
        release_status="released",
        delivery_status="delivered",
        generation_status="completed",
        qa_status="passed",
        editorial_status="completed",
        released_docx_path=document.docx_path,
    )
    db_session.add(case)
    await db_session.commit()

    await upload_custom_requirements(
        request=MagicMock(),
        document_id=document.id,
        file=_text_upload("Nuove regole obbligatorie dell'università."),
        current_user=user,
        db=db_session,
    )

    await db_session.refresh(document)
    await db_session.refresh(case)
    assert document.status == "draft"
    assert case.release_status == "blocked"
    assert case.delivery_status == "not_ready"
    assert case.released_docx_path is None
    assert case.generation_status == "not_started"
    assert case.qa_status == "no_data"


@pytest.mark.asyncio
async def test_methodology_cannot_change_during_active_generation(db_session):
    user = User(email="running-methodology-owner@example.com")
    db_session.add(user)
    await db_session.flush()
    document = Document(
        user_id=user.id,
        title="Running Thesis",
        topic="Governance of Italian university information systems",
        status="generating",
        additional_requirements="Original methodology.",
    )
    db_session.add(document)
    await db_session.flush()
    db_session.add(
        AIGenerationJob(
            user_id=user.id,
            document_id=document.id,
            job_type="full_document",
            status="running",
        )
    )
    await db_session.commit()

    with pytest.raises(HTTPException) as exc_info:
        await upload_custom_requirements(
            request=MagicMock(),
            document_id=document.id,
            file=_text_upload("Rules arriving too late."),
            current_user=user,
            db=db_session,
        )

    assert exc_info.value.status_code == status.HTTP_409_CONFLICT
    await db_session.refresh(document)
    assert document.additional_requirements == "Original methodology."
