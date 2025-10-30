"""
Database configuration and session management
"""

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from app.core.config import settings
import logging
import time
from sqlalchemy import event
import sqlalchemy

logger = logging.getLogger(__name__)

# Create async engine
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,  # MUST be False in production
    pool_size=20,
    max_overflow=40,
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args={
        "server_settings": {"jit": "off"},
        "command_timeout": 60,
    },
    future=True,
)

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

