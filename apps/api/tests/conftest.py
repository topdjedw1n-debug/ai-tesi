"""
Pytest configuration - sets environment variables BEFORE any imports
This ensures DATABASE_URL is set before database.py is imported
"""

import asyncio
import os
import pathlib
from importlib import import_module

import pytest

# SYSTEMIC .env ISOLATION: point Settings' env_file at /dev/null so the test
# process NEVER reads apps/api/.env. Every setdefault below used to be a
# point-fix against one .env leak (live Crossref, live Anthropic fallback...);
# the last straw was HUMANIZER_PROVIDER/HUMANIZER_MODEL from a developer's
# .env redirecting test_humanize_anthropic past its mock into a REAL paid
# OpenAI gpt-4 call (03.07.2026). With ENV_FILE=os.devnull the suite runs
# exactly like CI (no .env): code defaults + the explicit values below.
# Must be set before app.core.config is imported (it resolves ENV_FILE once,
# at Settings class definition).
os.environ["ENV_FILE"] = os.devnull

# Set environment variables BEFORE any test imports
# This runs BEFORE pytest collects tests, ensuring database.py sees the correct DATABASE_URL
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ENVIRONMENT", "test")
os.environ.setdefault("DISABLE_RATE_LIMIT", "true")
os.environ.setdefault(
    "CORS_ALLOWED_ORIGINS", "http://localhost:3000"
)  # Single origin for tests
# Stripe test credentials must be set HERE: per-module os.environ.setdefault
# calls in test files run after Settings is instantiated (this conftest
# imports app.core.database below), so in CI - where there is no .env file -
# the webhook endpoint saw STRIPE_WEBHOOK_SECRET=None and returned
# "Webhook secret not configured". Values are arbitrary: all webhook tests
# mock stripe.Webhook.construct_event; the endpoint only needs non-None.
os.environ.setdefault("STRIPE_SECRET_KEY", "sk_test_ci_default")
os.environ.setdefault("STRIPE_WEBHOOK_SECRET", "whsec_test_ci_default")
# Source grounding must stay OFF in tests unless a test enables it explicitly
# (init kwargs beat env vars). A developer's .env legitimately turns it on for
# real runs — without this guard, pipeline tests that build Settings() from
# .env start hitting LIVE Crossref/OpenAlex to build source packs (observed:
# 19-minute suite, 8 network-dependent failures).
os.environ.setdefault("SOURCE_GROUNDING_ENABLED", "false")
os.environ.setdefault("GROUNDING_GATE_ENABLED", "false")
# Second-layer QA (Stage B5) must stay OFF in tests unless a test enables it
# explicitly (init kwargs beat env vars). A developer's .env legitimately
# turns claim verification + reviewer panel on for real runs — without this
# guard, tests that build Settings() from .env hit extra LLM stages and the
# CLAIM_VERIFICATION_ENABLED-requires-CITATION_VERIFICATION_ENABLED validator.
os.environ.setdefault("CLAIM_VERIFICATION_ENABLED", "false")
os.environ.setdefault("QUALITY_PANEL_ENABLED", "false")
# Same leak class: a developer's .env enables the citation verifier for real
# runs; unguarded, pipeline tests that don't patch CitationVerifier run the
# live Step 4.7 stage (Crossref/OpenAlex/S2 lookups) against the network.
os.environ.setdefault("CITATION_VERIFICATION_ENABLED", "false")
# App-lifespan tests must not start a real polling loop against the shared
# module database. Worker behavior has focused tests with explicit instances.
os.environ.setdefault("GENERATION_WORKER_ENABLED", "false")
# Most of the legacy unit suite predates the narrow Italian intake contour.
# Keep those tests explicit about exercising legacy behavior; code and sample
# runtime defaults stay fail-closed for real deployments.
os.environ.setdefault("METHODOLOGY_REQUIRED_FOR_GENERATION", "false")
os.environ.setdefault("LEGACY_GENERATION_ENDPOINTS_ENABLED", "true")
# Same leak class: the developer's .env points the fallback chain at LIVE
# Anthropic models (OpenAI quota outage, 02.07.2026); tests that mock only
# OpenAI would silently make real Anthropic calls. Pin the code default.
os.environ.setdefault(
    "AI_FALLBACK_CHAIN",
    "openai:gpt-4,openai:gpt-3.5-turbo,anthropic:claude-sonnet-5",
)

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.core import database as _database
from app.core.database import AsyncSessionLocal, Base, get_engine


@pytest.fixture(scope="session", autouse=True)
def _remove_stale_db_files():
    """Leftover DB files from previous runs leak data into the next run
    (UNIQUE constraint flakes on fixed fixture emails). Remove them up front."""
    for name in ("test.db", "test_integration_simple.db"):
        pathlib.Path(name).unlink(missing_ok=True)
    yield


@pytest.fixture(scope="module", autouse=True)
def _isolated_database(tmp_path_factory):
    """Give every test module its own SQLite file and engine.

    The app caches a single engine globally and binds one sessionmaker to it,
    so all test files used to share ./test.db — any row left behind by one file
    (e.g. users created through the app's get_db without a drop_all teardown)
    broke unrelated files later in the run. A per-module engine on a fresh tmp
    file makes each file start exactly like a standalone run.

    NullPool: pooled aiosqlite connections must not be reused across the
    function-scoped event loops pytest-asyncio creates per test.
    """
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}", poolclass=NullPool)
    _database._engine = engine
    # Every consumer (tests and app code alike) holds the same sessionmaker
    # object created via the module __getattr__ — rebind it to the new engine.
    AsyncSessionLocal.configure(bind=engine)

    async def _create_schema() -> None:
        # Ensure all models are registered on Base.metadata before create_all
        for module_name in ("admin", "auth", "document", "payment", "refund", "user"):
            import_module(f"app.models.{module_name}")

        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    # No event loop is running between modules, so asyncio.run is safe here
    asyncio.run(_create_schema())
    yield
    asyncio.run(engine.dispose())


@pytest.fixture
async def db_session():
    """Create a test database session"""
    # Create tables
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create session
    async with AsyncSessionLocal() as session:
        yield session

    # Clean up after test
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture(scope="session")
def redis_available() -> bool:
    """
    Layer 3 of Defense-in-Depth: Check if Redis is available for testing.

    Use with @pytest.mark.skipif(not redis_available) for Redis-dependent tests.

    Returns:
        bool: True if Redis is reachable, False otherwise

    See: .github/BUG_FIX_PLAN.md → Bug #1 → Layer 3
    """
    import redis.exceptions

    try:
        # Synchronous check for session-scoped fixture
        import redis

        client = redis.from_url(os.environ.get("REDIS_URL", "redis://localhost:6379/0"))
        client.ping()
        client.close()
        return True
    except (redis.exceptions.ConnectionError, Exception):
        return False
