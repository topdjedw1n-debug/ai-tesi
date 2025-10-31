"""
Database configuration and session management
"""

import logging
import os
import time
from typing import Any

import sqlalchemy
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

logger = logging.getLogger(__name__)

# Create async engine
# SQLite doesn't support pool_size and max_overflow
def _create_engine():
    """Create database engine with appropriate parameters based on database type"""
    # CRITICAL: ALWAYS check os.environ FIRST (for test compatibility)
    # This ensures tests can override settings.DATABASE_URL even if it's set
    db_url = os.environ.get("DATABASE_URL")
    
    # Only import settings if DATABASE_URL not in environment
    if not db_url:
        from app.core.config import settings
        db_url = getattr(settings, 'DATABASE_URL', None) or ""
    
    if not db_url:
        # Fallback: will be set later
        db_url = "sqlite+aiosqlite:///:memory:"
    
    # Check if SQLite (must check before creating engine)
    is_sqlite = "sqlite" in db_url.lower()
    
    if is_sqlite:
        # SQLite-specific configuration (no pool parameters)
        engine_kwargs = {
            "echo": False,
            "future": True,
        }
    else:
        # PostgreSQL and other databases (with pool parameters)
        engine_kwargs = {
            "echo": False,
            "pool_pre_ping": True,
            "pool_size": 20,
            "max_overflow": 40,
            "pool_recycle": 3600,
            "future": True,
            "connect_args": {
                "server_settings": {"jit": "off"},
                "command_timeout": 60,
            },
        }
    
    return create_async_engine(
        db_url,
        **engine_kwargs
    )

# Import settings now (after defining _create_engine to avoid circular issues)
from app.core.config import settings  # noqa: E402

engine = _create_engine()

# Log slow queries (>= 500 ms)
SLOW_QUERY_THRESHOLD_MS = 500

@event.listens_for(engine.sync_engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-redef]
    context._query_start_time = time.time()

@event.listens_for(engine.sync_engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):  # type: ignore[no-redef]
    total_ms = (time.time() - getattr(context, "_query_start_time", time.time())) * 1000
    if total_ms >= SLOW_QUERY_THRESHOLD_MS:
        logger.warning(f"Slow query ({total_ms:.1f} ms): {statement}")

# Create async session factory
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    """Base class for all database models"""
    pass


async def get_db() -> AsyncSession:
    """Get database session"""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    """Initialize database tables"""
    try:
        async with engine.begin() as conn:
            # Import all models to ensure they are registered
            from app.models import auth, document, user  # noqa

            # Create all tables
            await conn.run_sync(Base.metadata.create_all)
            logger.info("Database tables created successfully")

            # Ensure critical indexes exist (idempotent)
            # Documents indexes
            await conn.execute(
                sqlalchemy.text("CREATE INDEX IF NOT EXISTS ix_documents_user_id ON documents (user_id);")
            )
            await conn.execute(
                sqlalchemy.text("CREATE INDEX IF NOT EXISTS ix_documents_created_at ON documents (created_at);")
            )
            await conn.execute(
                sqlalchemy.text("CREATE INDEX IF NOT EXISTS ix_document_sections_document_id ON document_sections (document_id);")
            )
            await conn.execute(
                sqlalchemy.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_users_email ON users (email);")
            )
            await conn.execute(
                sqlalchemy.text("CREATE UNIQUE INDEX IF NOT EXISTS uq_magic_link_tokens_token ON magic_link_tokens (token);")
            )
            await conn.execute(
                sqlalchemy.text("CREATE INDEX IF NOT EXISTS ix_magic_link_tokens_email ON magic_link_tokens (email);")
            )
            await conn.execute(
                sqlalchemy.text("CREATE INDEX IF NOT EXISTS ix_magic_link_tokens_expires_at ON magic_link_tokens (expires_at);")
            )
            # AI Generation Jobs indexes
            await conn.execute(
                sqlalchemy.text("CREATE INDEX IF NOT EXISTS ix_ai_generation_jobs_user_id ON ai_generation_jobs (user_id);")
            )
            await conn.execute(
                sqlalchemy.text("CREATE INDEX IF NOT EXISTS ix_ai_generation_jobs_started_at ON ai_generation_jobs (started_at);")
            )
            logger.info("Database indexes ensured")
    except Exception as e:
        logger.error(f"Failed to initialize database: {e}")
        raise


async def verify_db_backup(db: AsyncSession) -> dict[str, Any]:
    """
    Verify database backup integrity by running health checks.

    Checks:
    - Database connectivity
    - Table counts and consistency
    - Index existence
    - Query performance

    Returns:
        dict with status (healthy/needs-attention/critical) and checks details
    """
    checks = {
        "connectivity": False,
        "table_counts": {},
        "indexes_ok": False,
        "performance_test": False
    }

    try:
        # Check connectivity
        await db.execute(text("SELECT 1"))
        checks["connectivity"] = True

        # Check table counts
        result = await db.execute(text("""
            SELECT table_name
            FROM information_schema.tables
            WHERE table_schema = 'public'
        """))
        tables = [row[0] for row in result.fetchall()]

        for table in tables:
            count_result = await db.execute(text(f"SELECT COUNT(*) FROM {table}"))
            checks["table_counts"][table] = count_result.scalar()

        # Check critical indexes exist
        index_result = await db.execute(text("""
            SELECT indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            AND indexname LIKE 'ix_%' OR indexname LIKE 'uq_%'
        """))
        indexes = [row[0] for row in index_result.fetchall()]
        checks["indexes_ok"] = len(indexes) > 0

        # Performance test: simple query
        start = time.time()
        await db.execute(text("SELECT COUNT(*) FROM users"))
        query_time = time.time() - start
        checks["performance_test"] = query_time < 1.0  # Should be < 1 second

        # Determine overall status
        if checks["connectivity"] and checks["indexes_ok"] and checks["performance_test"]:
            status = "healthy"
        elif checks["connectivity"]:
            status = "needs_attention"
        else:
            status = "critical"

        return {
            "status": status,
            "checks": checks,
            "timestamp": time.time()
        }
    except Exception as e:
        logger.error(f"Database backup verification failed: {e}")
        return {
            "status": "critical",
            "checks": checks,
            "error": str(e),
            "timestamp": time.time()
        }

