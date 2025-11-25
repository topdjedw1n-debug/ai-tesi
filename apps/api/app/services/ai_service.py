"""
from typing import Optional
AI service for generating content using various providers
"""

import logging
import time
from datetime import date, datetime
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import AIProviderError, NotFoundError
from app.models.auth import User
from app.models.document import Document, DocumentOutline, DocumentSection
from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.ai_pipeline.generator import SectionGenerator
from app.services.circuit_breaker import CircuitBreaker
from app.services.cost_estimator import CostEstimator
from app.services.retry_strategy import RetryStrategy

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI content generation"""

    def __init__(self, db: AsyncSession):
        self.db = db
        # Initialize circuit breakers for each provider
        self._openai_circuit = CircuitBreaker(failure_threshold=5, recovery_timeout=60)
        self._anthropic_circuit = CircuitBreaker(
            failure_threshold=5, recovery_timeout=60
        )
        # Initialize retry strategies with circuit breakers
        self._openai_retry = RetryStrategy(
            max_retries=3, delays=[2, 4, 8], circuit_breaker=self._openai_circuit
        )
        self._anthropic_retry = RetryStrategy(
            max_retries=3, delays=[2, 4, 8], circuit_breaker=self._anthropic_circuit
        )

    async def _check_daily_token_limit(self) -> None:
        """Check if daily token limit is exceeded (optional)"""
        if settings.DAILY_TOKEN_LIMIT is None:
            return  # Daily limit disabled

        try:
            # Get start of today
            today_start = datetime.combine(date.today(), datetime.min.time())

            # Calculate total tokens used today
            today_tokens_result = await self.db.execute(
                select(func.sum(Document.tokens_used)).where(
                    Document.created_at >= today_start
                )
            )
            today_tokens = today_tokens_result.scalar() or 0

            if today_tokens >= settings.DAILY_TOKEN_LIMIT:
                logger.warning(
                    f"Daily token limit exceeded: {today_tokens}/{settings.DAILY_TOKEN_LIMIT}"
                )
                # Note: According to task, we can continue or raise error
                # For now, just log a warning and continue
        except Exception as e:
            logger.error(f"Error checking daily token limit: {e}")
            # Don't fail the request if limit check fails

    async def generate_outline(
        self, document_id: int, user_id: int, additional_requirements: str | None = None
    ) -> dict[str, Any]:
        """Generate document outline using AI"""
        try:
            # Get document
            result = await self.db.execute(
                select(Document).where(
                    Document.id == document_id, Document.user_id == user_id
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise NotFoundError("Document not found")

            # Check daily token limit (optional)
            await self._check_daily_token_limit()

            # Generate outline using AI
            start_time = time.time()
            outline_data = await self._call_ai_provider(
                provider=document.ai_provider,
                model=document.ai_model,
                prompt=self._build_outline_prompt(document, additional_requirements),
            )

            generation_time = int(time.time() - start_time)

            # Save outline
            outline = DocumentOutline(
                document_id=document_id,
                outline_data=outline_data,
                total_sections=len(outline_data.get("sections", [])),
                ai_provider=document.ai_provider,
                ai_model=document.ai_model,
                tokens_used=outline_data.get("tokens_used", 0),
                generation_time_seconds=generation_time,
            )

            self.db.add(outline)

            # Get tokens used from response
            tokens_used = outline_data.get("tokens_used", 0)

            # Update document status
            await self.db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    outline=outline_data,
                    status="outline_generated",
                    tokens_used=Document.tokens_used + tokens_used,
                    generation_time_seconds=Document.generation_time_seconds
                    + generation_time,
                )
            )

            await self.db.commit()

            # Log token usage for monitoring
            logger.info(
                f"AI usage: doc={document_id}, model={document.ai_model}, "
                f"provider={document.ai_provider}, tokens={tokens_used}, "
                f"type=outline"
            )

            return {
                "document_id": document_id,
                "outline": outline_data,
                "status": "completed",
                "tokens_used": outline_data.get("tokens_used", 0),
                "generation_time_seconds": generation_time,
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error generating outline: {e}")
            raise AIProviderError(f"Failed to generate outline: {str(e)}") from e

    async def estimate_generation_cost(
        self,
        document_id: int,
        user_id: int,
        include_humanization: bool = False,
    ) -> dict[str, Any]:
        """
        Estimate cost for generating a document before starting

        Args:
            document_id: Document ID
            user_id: User ID
            include_humanization: Whether humanization will be used

        Returns:
            Cost estimation dictionary
        """
        try:
            # Get document
            result = await self.db.execute(
                select(Document).where(
                    Document.id == document_id, Document.user_id == user_id
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise NotFoundError("Document not found")

            # Estimate cost
            cost_estimate = CostEstimator.estimate_document_cost(
                provider=document.ai_provider,
                model=document.ai_model,
                target_pages=document.target_pages,
                include_rag=True,  # Always enabled now
                include_humanization=include_humanization,
            )

            return cost_estimate

        except Exception as e:
            logger.error(f"Error estimating cost: {e}")
            raise AIProviderError(f"Failed to estimate cost: {str(e)}") from e

    async def generate_section(
        self,
        document_id: int,
        section_title: str,
        section_index: int,
        user_id: int,
        additional_requirements: str | None = None,
    ) -> dict[str, Any]:
        """Generate a specific section using AI with RAG"""
        try:
            # Get document
            result = await self.db.execute(
                select(Document).where(
                    Document.id == document_id, Document.user_id == user_id
                )
            )
            document = result.scalar_one_or_none()

            if not document:
                raise NotFoundError("Document not found")

            # Check daily token limit (optional)
            await self._check_daily_token_limit()

            # Use SectionGenerator for RAG-enhanced generation
            start_time = time.time()
            section_generator = SectionGenerator()

            # Get previously generated sections for context
            context_result = await self.db.execute(
                select(DocumentSection)
                .where(DocumentSection.document_id == document_id)
                .where(DocumentSection.section_index < section_index)
                .order_by(DocumentSection.section_index)
            )
            context_sections = []
            for prev_section in context_result.scalars().all():
                context_sections.append(
                    {
                        "title": prev_section.title,
                        "content": prev_section.content or "",
                    }
                )

            # Generate section with RAG
            section_result = await section_generator.generate_section(
                document=document,
                section_title=section_title,
                section_index=section_index,
                provider=document.ai_provider,
                model=document.ai_model,
                citation_style=CitationStyle.APA,  # Default to APA
                humanize=False,  # Can be made configurable later
                context_sections=context_sections if context_sections else None,
                additional_requirements=additional_requirements,
            )

            generation_time = int(time.time() - start_time)

            # Estimate tokens used (approximate: ~4 chars per token)
            # This is a rough estimate since SectionGenerator doesn't return token count
            content_length = len(section_result.get("content", ""))
            estimated_tokens = max(content_length // 4, 100)  # Minimum 100 tokens

            # Save or update section
            result = await self.db.execute(
                select(DocumentSection).where(
                    DocumentSection.document_id == document_id,
                    DocumentSection.section_index == section_index,
                )
            )
            section = result.scalar_one_or_none()

            content = section_result.get("content", "")
            if section:
                section.content = content
                section.status = "completed"
                section.tokens_used = estimated_tokens
                section.generation_time_seconds = generation_time
                section.completed_at = datetime.utcnow()
            else:
                section = DocumentSection(
                    document_id=document_id,
                    title=section_title,
                    section_index=section_index,
                    content=content,
                    status="completed",
                    tokens_used=estimated_tokens,
                    generation_time_seconds=generation_time,
                    completed_at=datetime.utcnow(),
                )
                self.db.add(section)

            # Update document tokens and time
            await self.db.execute(
                update(Document)
                .where(Document.id == document_id)
                .values(
                    tokens_used=Document.tokens_used + estimated_tokens,
                    generation_time_seconds=Document.generation_time_seconds
                    + generation_time,
                )
            )

            await self.db.commit()

            # Log token usage for monitoring
            logger.info(
                f"AI usage: doc={document_id}, model={document.ai_model}, "
                f"provider={document.ai_provider}, tokens={estimated_tokens}, "
                f"type=section, section_index={section_index}, sources={section_result.get('sources_used', 0)}"
            )

            return {
                "document_id": document_id,
                "section_title": section_title,
                "section_index": section_index,
                "content": content,
                "status": "completed",
                "tokens_used": estimated_tokens,
                "generation_time_seconds": generation_time,
                "citations": section_result.get("citations", []),
                "bibliography": section_result.get("bibliography", []),
                "sources_used": section_result.get("sources_used", 0),
            }

        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error generating section: {e}")
            raise AIProviderError(f"Failed to generate section: {str(e)}") from e

    async def get_user_usage(self, user_id: int) -> dict[str, Any]:
        """Get AI usage statistics for a user"""
        try:
            # Get total documents and tokens used from User model
            result = await self.db.execute(
                select(
                    func.coalesce(User.total_documents_created, 0).label(
                        "total_documents"
                    ),
                    func.coalesce(User.total_tokens_used, 0).label("total_tokens"),
                ).where(User.id == user_id)
            )
            stats = result.first()

            return {
                "user_id": user_id,
                "total_documents": stats.total_documents if stats else 0,
                "total_tokens_used": stats.total_tokens if stats else 0,
                "last_updated": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error getting user usage: {e}")
            raise AIProviderError(f"Failed to get usage statistics: {str(e)}") from e

    async def _call_ai_provider(
        self, provider: str, model: str, prompt: str
    ) -> dict[str, Any]:
        """Call the appropriate AI provider"""
        if provider == "openai":
            return await self._call_openai(model, prompt)
        elif provider == "anthropic":
            return await self._call_anthropic(model, prompt)
        else:
            raise AIProviderError(f"Unsupported AI provider: {provider}")

    async def _call_openai(self, model: str, prompt: str) -> dict[str, Any]:
        """Call OpenAI API with circuit breaker and retry"""

        async def _make_request():
            import openai

            if not settings.OPENAI_API_KEY:
                raise AIProviderError("OpenAI API key not configured")

            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert academic writer specializing in thesis and research paper generation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4000,
                temperature=0.7,
            )

            content = response.choices[0].message.content
            tokens_used = response.usage.total_tokens if response.usage else 0

            return {"content": content, "tokens_used": tokens_used}

        # Call with retry strategy and circuit breaker
        return await self._openai_retry.execute_with_retry(_make_request)

    async def _call_anthropic(self, model: str, prompt: str) -> dict[str, Any]:
        """Call Anthropic API with circuit breaker and retry"""

        async def _make_request():
            import anthropic

            if not settings.ANTHROPIC_API_KEY:
                raise AIProviderError("Anthropic API key not configured")

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            response = await client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0.7,
                system="You are an expert academic writer specializing in thesis and research paper generation.",
                messages=[{"role": "user", "content": prompt}],
            )

            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens

            return {"content": content, "tokens_used": tokens_used}

        # Call with retry strategy and circuit breaker
        return await self._anthropic_retry.execute_with_retry(_make_request)

    def _build_outline_prompt(
        self, document: Document, additional_requirements: str | None = None
    ) -> str:
        """Build prompt for outline generation"""
        prompt = f"""
Generate a detailed academic thesis outline for the following topic:

Topic: {document.topic}
Language: {document.language}
Target Pages: {document.target_pages}

Please provide a structured outline with:
1. Introduction
2. Literature Review
3. Methodology
4. Results/Analysis
5. Discussion
6. Conclusion
7. References

For each section, include:
- Main points to cover
- Sub-sections
- Estimated word count
- Key concepts to address

Additional Requirements: {additional_requirements or 'None specified'}

Please respond with a JSON structure containing the outline data.
"""
        return prompt.strip()
