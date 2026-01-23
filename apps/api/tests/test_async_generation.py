"""
Tests for async document generation with job tracking
"""
import pytest

from app.models.auth import User
from app.models.document import AIGenerationJob, Document


@pytest.mark.asyncio
async def test_async_generation_creates_job(db_session):
    """Test that async generation request creates a job in the database"""
    # Create user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id, title="Test Thesis", topic="AI in Education", status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create job
    job = AIGenerationJob(
        document_id=document.id,
        user_id=user.id,
        job_type="document_generation",
        status="queued",
        progress=0,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Verify job was created
    assert job.id is not None
    assert job.status == "queued"
    assert job.progress == 0
    assert job.document_id == document.id


@pytest.mark.asyncio
async def test_job_status_updates(db_session):
    """Test that job status can be updated"""
    # Create user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id, title="Test Thesis", topic="AI in Education", status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create job
    job = AIGenerationJob(
        document_id=document.id,
        user_id=user.id,
        job_type="document_generation",
        status="queued",
        progress=0,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Update to running
    from sqlalchemy import update

    await db_session.execute(
        update(AIGenerationJob)
        .where(AIGenerationJob.id == job.id)
        .values(status="running", progress=50)
    )
    await db_session.commit()
    await db_session.refresh(job)

    assert job.status == "running"
    assert job.progress == 50


@pytest.mark.asyncio
async def test_job_completes_successfully(db_session):
    """Test that job can be marked as completed"""
    # Create user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id, title="Test Thesis", topic="AI in Education", status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create job
    job = AIGenerationJob(
        document_id=document.id,
        user_id=user.id,
        job_type="document_generation",
        status="running",
        progress=50,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Mark as completed
    from datetime import datetime

    from sqlalchemy import update

    await db_session.execute(
        update(AIGenerationJob)
        .where(AIGenerationJob.id == job.id)
        .values(status="completed", progress=100, completed_at=datetime.utcnow())
    )
    await db_session.commit()
    await db_session.refresh(job)

    assert job.status == "completed"
    assert job.progress == 100
    assert job.completed_at is not None


@pytest.mark.asyncio
async def test_job_fails_gracefully(db_session):
    """Test that job can be marked as failed"""
    # Create user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id, title="Test Thesis", topic="AI in Education", status="draft"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create job
    job = AIGenerationJob(
        document_id=document.id,
        user_id=user.id,
        job_type="document_generation",
        status="running",
        progress=30,
    )
    db_session.add(job)
    await db_session.commit()
    await db_session.refresh(job)

    # Mark as failed
    from datetime import datetime

    from sqlalchemy import update

    await db_session.execute(
        update(AIGenerationJob)
        .where(AIGenerationJob.id == job.id)
        .values(
            status="failed",
            error_message="Test error message",
            success=False,
            completed_at=datetime.utcnow(),
        )
    )
    await db_session.commit()
    await db_session.refresh(job)

    assert job.status == "failed"
    assert job.error_message == "Test error message"
    assert job.success is False
    assert job.completed_at is not None
