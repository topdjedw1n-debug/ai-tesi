"""
Unit tests for AIService
"""

import pytest

from app.core.exceptions import AIProviderError
from app.models.auth import User
from app.models.document import Document
from app.services.ai_service import AIService


@pytest.mark.asyncio
async def test_get_user_usage_correctness(db_session):
    """Test getting user usage statistics correctly"""
    # Create test user
    user = User(
        email="test@example.com",
        full_name="Test User",
        total_documents_created=5,
        total_tokens_used=1000
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create service
    service = AIService(db_session)

    # Get usage stats
    result = await service.get_user_usage(user_id=user.id)

    # Verify result
    assert result["user_id"] == user.id
    assert result["total_documents"] == 5
    assert result["total_tokens_used"] == 1000
    assert "last_updated" in result


@pytest.mark.asyncio
async def test_generate_outline_not_found(db_session):
    """Test generating outline for non-existent document raises AIProviderError"""
    # Create service
    service = AIService(db_session)

    # Try to generate outline for non-existent document
    with pytest.raises(AIProviderError, match="Failed to generate outline"):
        await service.generate_outline(
            document_id=999,
            user_id=1,
            additional_requirements=None
        )


@pytest.mark.asyncio
async def test_build_outline_prompt(db_session):
    """Test building outline prompt"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id,
        title="Test Thesis",
        topic="AI in Education",
        language="en",
        target_pages=15,
        ai_provider="openai",
        ai_model="gpt-4"
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create service
    service = AIService(db_session)

    # Build prompt
    prompt = service._build_outline_prompt(document, additional_requirements="Be thorough")

    # Verify prompt structure
    assert "AI in Education" in prompt
    assert "en" in prompt
    assert "15" in prompt
    assert "Be thorough" in prompt
    assert "Introduction" in prompt
    assert "Literature Review" in prompt


@pytest.mark.asyncio
async def test_build_section_prompt(db_session):
    """Test building section prompt"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document
    document = Document(
        user_id=user.id,
        title="Test Thesis",
        topic="AI in Education",
        language="en",
        target_pages=15
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create service
    service = AIService(db_session)

    # Build prompt using PromptBuilder (not AIService private method)
    from app.services.ai_pipeline.prompt_builder import PromptBuilder
    prompt = PromptBuilder.build_section_prompt(
        document=document,
        section_title="Introduction",
        section_index=0,
        additional_requirements="Use formal academic style"
    )

    # Verify prompt structure
    assert document.topic in prompt
    assert "Introduction" in prompt
    assert "0" in prompt or "Section Index: 0" in prompt
    assert "Use formal academic style" in prompt
    assert "academic" in prompt.lower()


@pytest.mark.asyncio
async def test_call_openai_missing_api_key(db_session):
    """Test calling OpenAI without API key raises error"""
    from app.core.config import settings

    # Save original key
    original_key = settings.OPENAI_API_KEY

    # Create service
    service = AIService(db_session)

    # Remove API key
    settings.OPENAI_API_KEY = None

    try:
        # Try to call OpenAI
        with pytest.raises(AIProviderError, match="OpenAI API key not configured"):
            await service._call_openai(model="gpt-4", prompt="Test prompt")
    finally:
        # Restore original key
        settings.OPENAI_API_KEY = original_key


@pytest.mark.asyncio
async def test_call_anthropic_missing_api_key(db_session):
    """Test calling Anthropic without API key raises error"""
    from app.core.config import settings

    # Save original key
    original_key = settings.ANTHROPIC_API_KEY

    # Create service
    service = AIService(db_session)

    # Remove API key
    settings.ANTHROPIC_API_KEY = None

    try:
        # Try to call Anthropic
        with pytest.raises(AIProviderError, match="Anthropic API key not configured"):
            await service._call_anthropic(model="claude-3-opus", prompt="Test prompt")
    finally:
        # Restore original key
        settings.ANTHROPIC_API_KEY = original_key


@pytest.mark.asyncio
async def test_call_ai_provider_unsupported(db_session):
    """Test calling unsupported AI provider raises error"""
    service = AIService(db_session)

    with pytest.raises(AIProviderError, match="Unsupported AI provider"):
        await service._call_ai_provider(
            provider="unsupported_provider",
            model="test-model",
            prompt="Test prompt"
        )

