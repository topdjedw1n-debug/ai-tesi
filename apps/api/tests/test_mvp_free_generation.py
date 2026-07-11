"""
Stage 0 — MVP free-generation gate on POST /api/v1/generate/full-document.

Covers the two modes added in Stage 0:
  * sales mode (MVP_FREE_GENERATION_ENABLED=False): a completed Payment is
    required, otherwise 402 and no job is created;
  * free MVP mode (=True): generation runs without Stripe, but is bounded by
    a page cap (400), a per-user daily generation quota (429), and a daily
    token budget (429).

The background generation task is patched to a no-op so the endpoint is
exercised without triggering real AI calls.
"""
import os
from datetime import datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from httpx import AsyncClient

os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_mvp_gen.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_mock_key_not_used")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_mock_secret_not_used")

from sqlalchemy import func, select

from app.core.config import settings
from app.core.database import AsyncSessionLocal, Base, get_engine
from app.models.auth import User
from app.models.document import AIGenerationJob, Document
from app.models.payment import Payment
from main import app  # noqa: E402

FULL_DOCUMENT_URL = "/api/v1/generate/full-document"


@pytest.fixture
async def client():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        ac.headers.update(
            {
                "X-CSRF-Token": "test-csrf-token-for-integration-tests-1234567890",
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        yield ac


@pytest.fixture
async def db_session():
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def test_user(db_session):
    user = User(
        email="mvp-gen@example.com",
        full_name="MVP Gen User",
        is_active=True,
        is_verified=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def auth_token(client, test_user):
    from app.models.auth import MagicLinkToken

    token = MagicLinkToken(
        token="test_magic_link_token_mvp_gen",
        email=test_user.email,
        expires_at=datetime.utcnow() + timedelta(minutes=30),
    )
    async with AsyncSessionLocal() as session:
        session.add(token)
        await session.commit()

    response = await client.post(
        "/api/v1/auth/verify-magic-link",
        json={"token": "test_magic_link_token_mvp_gen"},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture(autouse=True)
def _no_background_generation(monkeypatch):
    """Stop the queued generation task from doing real work after the response."""
    monkeypatch.setattr(
        "app.api.v1.endpoints.generate.BackgroundJobService."
        "generate_full_document_async",
        AsyncMock(),
    )


async def _make_document(
    user_id: int,
    *,
    target_pages: int = 10,
    created_at: datetime | None = None,
) -> int:
    async with AsyncSessionLocal() as session:
        document = Document(
            user_id=user_id,
            title="Test Thesis",
            topic="AI in Education",
            status="draft",
            target_pages=target_pages,
            created_at=created_at,
            # These tests exercise the payment/quota gates; satisfy the
            # task-contract gate with a processed methodology.
            additional_requirements="Parsed methodology for gate tests",
            requirements_file_processed=True,
            citation_style="apa",
        )
        session.add(document)
        await session.commit()
        await session.refresh(document)
        return int(document.id)


async def _job_count(document_id: int) -> int:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(func.count(AIGenerationJob.id)).where(
                AIGenerationJob.document_id == document_id
            )
        )
        return int(result.scalar() or 0)


async def _document_status(document_id: int) -> str:
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(Document.status).where(Document.id == document_id)
        )
        return str(result.scalar_one())


# --------------------------------------------------------------------------
# Sales mode (free generation OFF) — payment gate
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sales_mode_without_payment_returns_402(
    client, test_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", False)
    document_id = await _make_document(test_user.id)

    response = await client.post(
        FULL_DOCUMENT_URL, json={"document_id": document_id}, headers=auth_headers
    )

    assert response.status_code == 402
    assert await _job_count(document_id) == 0
    assert await _document_status(document_id) == "draft"


@pytest.mark.asyncio
async def test_sales_mode_with_completed_payment_creates_job(
    client, test_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", False)
    document_id = await _make_document(test_user.id)
    async with AsyncSessionLocal() as session:
        session.add(
            Payment(
                user_id=test_user.id,
                document_id=document_id,
                amount=100.00,
                currency="EUR",
                status="completed",
            )
        )
        await session.commit()

    response = await client.post(
        FULL_DOCUMENT_URL, json={"document_id": document_id}, headers=auth_headers
    )

    assert response.status_code == 200
    assert "job_id" in response.json()
    assert await _job_count(document_id) == 1


# --------------------------------------------------------------------------
# Free MVP mode (free generation ON) — guardrails
# --------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_free_mode_without_payment_creates_job(
    client, test_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_MAX_PAGES", 20)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_DAILY_USER_LIMIT", 2)
    monkeypatch.setattr(settings, "DAILY_TOKEN_LIMIT", None)
    document_id = await _make_document(test_user.id, target_pages=10)

    response = await client.post(
        FULL_DOCUMENT_URL, json={"document_id": document_id}, headers=auth_headers
    )

    assert response.status_code == 200
    assert await _job_count(document_id) == 1


@pytest.mark.asyncio
async def test_free_mode_page_cap_returns_400(
    client, test_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_MAX_PAGES", 20)
    monkeypatch.setattr(settings, "DAILY_TOKEN_LIMIT", None)
    document_id = await _make_document(test_user.id, target_pages=50)

    response = await client.post(
        FULL_DOCUMENT_URL, json={"document_id": document_id}, headers=auth_headers
    )

    assert response.status_code == 400
    assert await _job_count(document_id) == 0
    assert await _document_status(document_id) == "draft"


@pytest.mark.asyncio
async def test_free_mode_daily_user_quota_returns_429(
    client, test_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_MAX_PAGES", 20)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_DAILY_USER_LIMIT", 2)
    monkeypatch.setattr(settings, "DAILY_TOKEN_LIMIT", None)
    document_id = await _make_document(test_user.id, target_pages=10)

    # Two generations already today (started_at defaults to now) -> at the cap.
    async with AsyncSessionLocal() as session:
        for _ in range(2):
            session.add(
                AIGenerationJob(
                    user_id=test_user.id,
                    document_id=document_id,
                    job_type="full_document",
                    status="completed",
                    progress=100,
                )
            )
        await session.commit()

    response = await client.post(
        FULL_DOCUMENT_URL, json={"document_id": document_id}, headers=auth_headers
    )

    assert response.status_code == 429
    # No new job beyond the two seeded ones.
    assert await _job_count(document_id) == 2


@pytest.mark.asyncio
async def test_free_mode_daily_token_budget_returns_429(
    client, test_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_MAX_PAGES", 20)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_DAILY_USER_LIMIT", 5)
    # Projected tokens = target_pages * TOKENS_PER_PAGE (20 * 1000 = 20000) > 500.
    monkeypatch.setattr(settings, "DAILY_TOKEN_LIMIT", 500)
    document_id = await _make_document(test_user.id, target_pages=20)

    response = await client.post(
        FULL_DOCUMENT_URL, json={"document_id": document_id}, headers=auth_headers
    )

    assert response.status_code == 429
    assert await _job_count(document_id) == 0
    assert await _document_status(document_id) == "draft"


@pytest.mark.asyncio
async def test_free_mode_daily_token_budget_counts_jobs_for_old_documents(
    client, test_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_MAX_PAGES", 20)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_DAILY_USER_LIMIT", 5)
    # Existing job tokens (400) + projected current doc (1000) exceeds this cap.
    monkeypatch.setattr(settings, "DAILY_TOKEN_LIMIT", 1200)

    old_document_id = await _make_document(
        test_user.id,
        target_pages=1,
        created_at=datetime.utcnow() - timedelta(days=1),
    )
    async with AsyncSessionLocal() as session:
        session.add(
            AIGenerationJob(
                user_id=test_user.id,
                document_id=old_document_id,
                job_type="full_document",
                status="completed",
                progress=100,
                total_tokens=400,
            )
        )
        await session.commit()

    document_id = await _make_document(test_user.id, target_pages=1)

    response = await client.post(
        FULL_DOCUMENT_URL, json={"document_id": document_id}, headers=auth_headers
    )

    assert response.status_code == 429
    assert await _job_count(document_id) == 0
    assert await _document_status(document_id) == "draft"


@pytest.mark.asyncio
async def test_free_mode_daily_token_budget_counts_active_projected_jobs(
    client, test_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_MAX_PAGES", 20)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_DAILY_USER_LIMIT", 5)
    # Active projected job (2000) + projected current doc (1000) exceeds this cap.
    monkeypatch.setattr(settings, "DAILY_TOKEN_LIMIT", 2500)

    active_document_id = await _make_document(test_user.id, target_pages=2)
    async with AsyncSessionLocal() as session:
        session.add(
            AIGenerationJob(
                user_id=test_user.id,
                document_id=active_document_id,
                job_type="full_document",
                status="running",
                progress=50,
                total_tokens=0,
            )
        )
        await session.commit()

    document_id = await _make_document(test_user.id, target_pages=1)

    response = await client.post(
        FULL_DOCUMENT_URL, json={"document_id": document_id}, headers=auth_headers
    )

    assert response.status_code == 429
    assert await _job_count(document_id) == 0
    assert await _document_status(document_id) == "draft"


@pytest.mark.asyncio
async def test_active_job_keeps_remaining_token_reservation_after_partial_usage(
    client, test_user, auth_headers, monkeypatch
):
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_ENABLED", True)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_MAX_PAGES", 20)
    monkeypatch.setattr(settings, "MVP_FREE_GENERATION_DAILY_USER_LIMIT", 5)
    # Existing 2-page job has spent 400/2000 tokens. Its remaining 1600 must
    # stay reserved: 400 actual + 1600 remaining + 1000 new > 2800.
    monkeypatch.setattr(settings, "DAILY_TOKEN_LIMIT", 2800)

    active_document_id = await _make_document(test_user.id, target_pages=2)
    async with AsyncSessionLocal() as session:
        session.add(
            AIGenerationJob(
                user_id=test_user.id,
                document_id=active_document_id,
                job_type="full_document",
                status="running",
                progress=50,
                total_tokens=400,
            )
        )
        await session.commit()

    document_id = await _make_document(test_user.id, target_pages=1)
    response = await client.post(
        FULL_DOCUMENT_URL, json={"document_id": document_id}, headers=auth_headers
    )

    assert response.status_code == 429
    assert await _job_count(document_id) == 0
    assert await _document_status(document_id) == "draft"
