"""Universal task contract: rules with sources, confirmation, honest basis."""


import pytest
from fastapi import HTTPException
from sqlalchemy import select

from app.api.v1.endpoints import documents as documents_endpoint
from app.models.auth import User
from app.models.document import Document, DocumentProvenance
from app.services.generation_contract import generation_contract_error
from app.services.task_contract import (
    build_task_contract,
    contract_confirmation_error,
    structure_directive,
    task_contract_sha256,
)


async def _seed(db_session, email: str, **overrides) -> tuple[User, Document]:
    user = User(email=email, full_name="Contract Test", is_active=True)
    db_session.add(user)
    await db_session.flush()
    fields = {
        "user_id": user.id,
        "title": "Tesi senza metodologia",
        "topic": "L'economia circolare nelle imprese italiane",
        "language": "it",
        "target_pages": 20,
        "citation_style": "apa",
        "status": "draft",
    }
    fields.update(overrides)
    document = Document(**fields)
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)
    await db_session.refresh(user)
    return user, document


@pytest.mark.asyncio
async def test_methodology_basis_needs_no_confirmation(db_session):
    _, document = await _seed(
        db_session,
        "contract-methodology@example.com",
        additional_requirements="Linee guida dell'università",
        requirements_file_processed=True,
        work_type="tesi_magistrale",
    )
    contract = build_task_contract(document)
    assert contract["basis"] == "university_methodology"
    assert contract["confirmation_required"] is False
    assert contract["assumptions"] == []
    assert contract_confirmation_error(document) is None
    assert generation_contract_error(document) is None
    assert structure_directive(document) is None
    # Honest labeling: methodology-based works may claim it.
    assert contract["basis_label"] == "university methodology"


@pytest.mark.asyncio
async def test_minimal_data_requires_confirmed_assumptions(db_session):
    """The no-methodology path: assumed rules are visible, generation is
    blocked until the manager confirms, and any input change re-blocks."""
    _, document = await _seed(db_session, "contract-minimal@example.com")

    contract = build_task_contract(document)
    assert contract["basis"] == "standard_academic"
    assert contract["confirmation_required"] is True
    assumed_keys = {r["key"] for r in contract["assumptions"]}
    assert assumed_keys == {"work_type", "structure"}
    assert all(r["source"] == "system_default" for r in contract["assumptions"])
    # Honest labeling: never "university requirements" without a methodology.
    assert "university" not in contract["basis_label"]

    assert contract_confirmation_error(document) is not None
    assert generation_contract_error(document) is not None

    document.contract_confirmed_sha256 = task_contract_sha256(document)
    assert contract_confirmation_error(document) is None
    assert generation_contract_error(document) is None

    # Changing an input shifts the fingerprint -> stale confirmation blocks.
    document.topic = "Un tema completamente diverso di ricerca"
    assert contract_confirmation_error(document) is not None


@pytest.mark.asyncio
async def test_structure_directive_follows_work_type(db_session):
    _, document = await _seed(
        db_session, "contract-directive@example.com", work_type="essay"
    )
    directive = structure_directive(document)
    assert directive is not None
    assert "essay" in directive
    assert "standard academic structure" in directive


@pytest.mark.asyncio
async def test_contract_endpoints_confirm_and_expose(db_session):
    user, document = await _seed(db_session, "contract-endpoint@example.com")

    get_handler = getattr(
        documents_endpoint.get_task_contract,
        "__wrapped__",
        documents_endpoint.get_task_contract,
    )
    contract = await get_handler(
        document_id=int(document.id), current_user=user, db=db_session
    )
    assert contract["confirmed"] is False
    assert contract["confirmation_required"] is True

    confirm_handler = getattr(
        documents_endpoint.confirm_task_contract,
        "__wrapped__",
        documents_endpoint.confirm_task_contract,
    )
    result = await confirm_handler(
        document_id=int(document.id), current_user=user, db=db_session
    )
    assert result["confirmed"] is True

    await db_session.refresh(document)
    assert document.contract_confirmed_sha256 == result["sha256"]
    assert contract_confirmation_error(document) is None

    events = (
        (
            await db_session.execute(
                select(DocumentProvenance).where(
                    DocumentProvenance.document_id == document.id,
                    DocumentProvenance.event_type == "task_contract_confirmed",
                )
            )
        )
        .scalars()
        .all()
    )
    assert len(events) == 1

    # Foreign user cannot even see the contract.
    stranger = User(
        email="contract-stranger@example.com", full_name="S", is_active=True
    )
    db_session.add(stranger)
    await db_session.commit()
    await db_session.refresh(stranger)
    with pytest.raises(HTTPException) as exc_info:
        await get_handler(
            document_id=int(document.id), current_user=stranger, db=db_session
        )
    assert exc_info.value.status_code == 404


def test_merged_pack_keeps_uploaded_sources_first():
    from app.services.ai_pipeline.rag_retriever import SourceDoc
    from app.services.ai_pipeline.source_pack import PackedSource, SourcePack
    from app.services.background_jobs import _merge_source_packs

    def _src(title, key, score=0.5):
        return PackedSource(
            SourceDoc(title=title, authors=["A"], year=2020), key, score
        )

    uploaded = SourcePack(
        document_id=1, topic="t", sources=[_src("Uploaded reading", "Rossi2020", 1.0)]
    )
    uploaded.passages = ["sentinel"]
    api = SourcePack(
        document_id=1,
        topic="t",
        sources=[
            _src("API paper one", "Rossi2020"),  # collides with uploaded key
            _src("API paper two", "Bianchi2021"),
        ],
    )

    merged = _merge_source_packs(uploaded, api)
    keys = merged.keys()
    assert keys[0] == "Rossi2020"  # uploaded stays first and unrenamed
    assert "Bianchi2021" in keys
    assert "Rossi2020b" in keys  # collided API source got a suffix
    assert merged.passages == ["sentinel"]
    assert merged.sources[0].on_topic_score == 1.0


def test_pipeline_wiring_for_contract_and_supplement():
    import inspect

    from app.services import background_jobs as bj

    src = inspect.getsource(bj.BackgroundJobService.generate_full_document)
    # Mandatory-only blockers run before the pack is built; API retrieval
    # supplements the uploaded pack instead of replacing it.
    assert src.index("uploaded_sources_blockers") < src.index(
        "build_uploaded_source_pack"
    )
    assert "_merge_source_packs" in src
    # The run records its honest contract basis and the structure directive
    # reaches the prompts for no-methodology works.
    assert "task_contract" in src
    assert "structure_directive" in src
