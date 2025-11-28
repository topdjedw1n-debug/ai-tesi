"""
Extended tests for AIService to improve coverage
"""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.exceptions import AIProviderError, NotFoundError
from app.models.auth import User
from app.models.document import Document, DocumentOutline
from app.services.ai_service import AIService


@pytest.mark.asyncio
async def test_get_user_usage_user_not_found(db_session):
    """Test getting usage for non-existent user"""
    service = AIService(db_session)

    # Should return zeros for non-existent user
    result = await service.get_user_usage(user_id=99999)
    assert result["user_id"] == 99999
    assert result["total_documents"] == 0
    assert result["total_tokens_used"] == 0


@pytest.mark.asyncio
async def test_generate_outline_success_mock(db_session):
    """Test generating outline successfully with mocked AI"""
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
        ai_model="gpt-4",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create service
    service = AIService(db_session)

    # Mock AI response
    mock_response = {
        "content": "1. Introduction\n2. Literature Review\n3. Methodology\n4. Results\n5. Conclusion"
    }

    with patch.object(
        service, "_call_ai_provider", new_callable=AsyncMock
    ) as mock_call:
        mock_call.return_value = mock_response

        result = await service.generate_outline(
            document_id=document.id,
            user_id=user.id,
            additional_requirements="Be thorough",
        )

        # Verify result
        assert "outline" in result
        assert result["document_id"] == document.id


@pytest.mark.asyncio
async def test_generate_section_success_mock(db_session):
    """Test generating section successfully with mocked AI"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document with outline
    document = Document(
        user_id=user.id,
        title="Test Thesis",
        topic="AI in Education",
        language="en",
        target_pages=15,
        ai_provider="openai",
        ai_model="gpt-4",
    )
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    # Create outline
    outline = DocumentOutline(
        document_id=document.id,
        outline_data='{"sections": [{"title": "Introduction", "index": 0}]}',
    )
    db_session.add(outline)
    await db_session.commit()

    # Create service
    service = AIService(db_session)

    # Mock SectionGenerator.generate_section method
    mock_section_result = {
        "content": "This is the introduction section content.",
        "citations": [],
        "metadata": {},
    }

    # Mock SectionGenerator class
    with patch("app.services.ai_service.SectionGenerator") as MockSectionGenerator:
        mock_generator = AsyncMock()
        mock_generator.generate_section.return_value = mock_section_result
        MockSectionGenerator.return_value = mock_generator

        result = await service.generate_section(
            document_id=document.id,
            user_id=user.id,
            section_title="Introduction",
            section_index=0,
            additional_requirements=None,
        )

        # Verify result
        assert "section_title" in result
        assert result["status"] == "completed"


@pytest.mark.asyncio
async def test_generate_section_document_not_found(db_session):
    """Test generating section for non-existent document"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    service = AIService(db_session)

    with pytest.raises((NotFoundError, AIProviderError)):
        await service.generate_section(
            document_id=999,
            user_id=user.id,
            section_title="Introduction",
            section_index=0,
        )


@pytest.mark.asyncio
@pytest.mark.skip(
    reason="AIService.generate_section() now works without outline (uses SectionGenerator directly)"
)
async def test_generate_section_outline_not_found(db_session):
    """Test generating section when outline doesn't exist"""
    # Create test user
    user = User(email="test@example.com", full_name="Test User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)

    # Create document without outline
    document = Document(user_id=user.id, title="Test Thesis", topic="AI in Education")
    db_session.add(document)
    await db_session.commit()
    await db_session.refresh(document)

    service = AIService(db_session)

    # Generate section - will fail because no outline, but may raise different error
    with pytest.raises((NotFoundError, AIProviderError)):
        await service.generate_section(
            document_id=document.id,
            user_id=user.id,
            section_title="Introduction",
            section_index=0,
        )


@pytest.mark.asyncio
async def test_call_openai_success_mock(db_session):
    """Test calling OpenAI successfully with mock"""
    from unittest.mock import patch

    from app.core.config import settings

    # Save original key
    original_key = settings.OPENAI_API_KEY
    settings.OPENAI_API_KEY = "test-key-123"

    service = AIService(db_session)

    # Create mock response
    mock_response = MagicMock()
    mock_response.choices = [MagicMock()]
    mock_response.choices[0].message.content = "Test response"
    mock_response.usage = MagicMock()
    mock_response.usage.total_tokens = 100

    # Create mock client
    mock_client = MagicMock()
    mock_client.chat.completions.create = AsyncMock(return_value=mock_response)

    # Create mock openai module with AsyncOpenAI class
    mock_openai_module = MagicMock()
    mock_openai_module.AsyncOpenAI = MagicMock(return_value=mock_client)

    # Patch builtins.__import__ to return our mock when importing openai
    original_import = __import__

    def mock_import(name, *args, **kwargs):
        if name == "openai":
            return mock_openai_module
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        result = await service._call_openai(model="gpt-4", prompt="Test prompt")

    assert result["content"] == "Test response"
    assert result["tokens_used"] == 100

    # Restore original key
    settings.OPENAI_API_KEY = original_key


@pytest.mark.asyncio
async def test_call_anthropic_success_mock(db_session):
    """Test calling Anthropic successfully with mock"""
    from unittest.mock import patch

    from app.core.config import settings

    # Save original key
    original_key = settings.ANTHROPIC_API_KEY
    settings.ANTHROPIC_API_KEY = "test-key-123"

    service = AIService(db_session)

    # Create mock response
    mock_response = MagicMock()
    mock_response.content = [MagicMock()]
    mock_response.content[0].text = "Test response"
    mock_response.usage = MagicMock()
    mock_response.usage.input_tokens = 50
    mock_response.usage.output_tokens = 50

    # Create mock client
    mock_client = MagicMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    # Create mock anthropic module with AsyncAnthropic class
    mock_anthropic_module = MagicMock()
    mock_anthropic_module.AsyncAnthropic = MagicMock(return_value=mock_client)

    # Patch builtins.__import__ to return our mock when importing anthropic
    original_import = __import__

    def mock_import(name, *args, **kwargs):
        if name == "anthropic":
            return mock_anthropic_module
        return original_import(name, *args, **kwargs)

    with patch("builtins.__import__", side_effect=mock_import):
        result = await service._call_anthropic(
            model="claude-3-opus", prompt="Test prompt"
        )

    assert result["content"] == "Test response"
    assert result["tokens_used"] == 100

    # Restore original key
    settings.ANTHROPIC_API_KEY = original_key
