"""
from typing import Optional
AI service for generating content using various providers
"""

import json
import logging
import time
from datetime import date, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

if TYPE_CHECKING:
    from app.services.ai_pipeline.source_pack import SourcePack

from app.core.config import settings
from app.core.exceptions import AIProviderError, NotFoundError
from app.models.auth import User
from app.models.document import Document, DocumentOutline, DocumentSection
from app.services.ai_pipeline.citation_formatter import CitationStyle
from app.services.ai_pipeline.generator import SectionGenerator
from app.services.circuit_breaker import CircuitBreaker
from app.services.cost_estimator import CostEstimator, UsageTracker
from app.services.retry_strategy import RetryStrategy

logger = logging.getLogger(__name__)


class AIService:
    """Service for AI content generation"""

    def __init__(self, db: AsyncSession, usage_tracker: "UsageTracker | None" = None):
        self.db = db
        # Optional UsageTracker: when set, every provider call records its
        # real response.usage here (covers outline, reviewer panel and claim
        # verifier, which all route through this service)
        self.usage_tracker = usage_tracker
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
        self,
        document_id: int,
        user_id: int,
        additional_requirements: str | None = None,
        *,
        source_pack: "SourcePack | None" = None,
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
                provider=str(document.ai_provider),
                model=str(document.ai_model),
                prompt=self._build_outline_prompt(
                    document, additional_requirements, source_pack=source_pack
                ),
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

            # Calculate estimated sections and word count from outline
            sections = outline_data.get("sections", [])
            estimated_sections = len(sections)
            estimated_word_count = sum(
                section.get("estimated_words", 0) for section in sections
            )

            return {
                "document_id": document_id,
                "outline": outline_data,
                "status": "completed",
                "tokens_used": outline_data.get("tokens_used", 0),
                "generation_time_seconds": generation_time,
                "estimated_sections": estimated_sections,
                "estimated_word_count": estimated_word_count,
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
                provider=str(document.ai_provider),
                model=str(document.ai_model),
                target_pages=int(document.target_pages),
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
            # Local tracker captures real provider usage for this call;
            # falls back to the char-count estimate if no usage was reported
            section_usage = self.usage_tracker or UsageTracker()
            section_usage_start = section_usage.snapshot()
            section_generator = SectionGenerator(usage_tracker=section_usage)

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
                provider=str(document.ai_provider),
                model=str(document.ai_model),
                citation_style=CitationStyle.APA,  # Default to APA
                humanize=False,  # Can be made configurable later
                context_sections=context_sections if context_sections else None,
                additional_requirements=additional_requirements,
            )

            generation_time = int(time.time() - start_time)

            # Prefer real usage recorded by the provider call; fall back to
            # the legacy char-count estimate when no usage was reported
            real_tokens = section_usage.total_tokens - section_usage_start
            if real_tokens > 0:
                estimated_tokens = real_tokens
            else:
                content_length = len(section_result.get("content", ""))
                estimated_tokens = max(content_length // 4, 100)  # Minimum 100

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
                section.status = "completed"  # type: ignore[assignment]
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

            # Persist bibliography for later export (parity with the
            # background path; assign NEW lists — JSON columns don't track
            # in-place mutation)
            section.bibliography = section_result.get("bibliography") or []
            section.pack_keys_used = section_result.get("pack_keys_used") or []

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

    async def call_with_fallback(
        self, prompt: str, purpose: str = "ai_call"
    ) -> dict[str, Any]:
        """
        Call the configured AI fallback chain with a raw prompt.

        Tries each (provider, model) from AI_FALLBACK_CHAIN_LIST in order
        (each provider already has retry + circuit breaker). When
        AI_ENABLE_FALLBACK is off, only the first chain entry is used.

        Returns:
            Provider response dict: parsed JSON keys when the model returned
            valid JSON, otherwise {"content": text}; always plus "tokens_used".

        Raises:
            AllProvidersFailedError: If every provider in the chain fails.
        """
        from app.core.exceptions import AllProvidersFailedError

        chain = settings.AI_FALLBACK_CHAIN_LIST
        if not settings.AI_ENABLE_FALLBACK:
            chain = chain[:1]

        last_error: Exception | None = None
        for provider, model in chain:
            try:
                return await self._call_ai_provider(provider, model, prompt)
            except Exception as e:
                last_error = e
                logger.warning(
                    f"❌ Failed {provider}/{model} for {purpose}: "
                    f"{type(e).__name__}: {str(e)[:200]}"
                )

        raise AllProvidersFailedError(
            f"All AI providers failed for {purpose}. Tried {len(chain)} provider(s). "
            f"Last error: {type(last_error).__name__ if last_error else 'unknown'}"
        )

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

        async def _make_request() -> dict[str, Any]:
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
            if self.usage_tracker is not None and response.usage:
                self.usage_tracker.add(
                    "openai",
                    model,
                    response.usage.prompt_tokens or 0,
                    response.usage.completion_tokens or 0,
                    purpose="ai_service",
                )

            # Parse JSON from content string
            try:
                parsed_content = json.loads(content)
                return {**parsed_content, "tokens_used": tokens_used}
            except json.JSONDecodeError:
                # If not valid JSON, return as-is
                return {"content": content, "tokens_used": tokens_used}

        # Call with retry strategy and circuit breaker
        return await self._openai_retry.execute_with_retry(_make_request)

    async def _call_anthropic(self, model: str, prompt: str) -> dict[str, Any]:
        """Call Anthropic API with circuit breaker and retry"""

        async def _make_request() -> dict[str, Any]:
            import anthropic

            if not settings.ANTHROPIC_API_KEY:
                raise AIProviderError("Anthropic API key not configured")

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            request_kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": 4000,
                "system": "You are an expert academic writer specializing in thesis and research paper generation.",
                "messages": [{"role": "user", "content": prompt}],
            }
            # Claude 4+/5 models reject sampling params with a 400; only the
            # legacy claude-3 family still accepts temperature.
            if model.startswith("claude-3"):
                request_kwargs["temperature"] = 0.7

            response = await client.messages.create(  # type: ignore[attr-defined]
                **request_kwargs
            )

            content = response.content[0].text
            tokens_used = response.usage.input_tokens + response.usage.output_tokens
            if self.usage_tracker is not None:
                self.usage_tracker.add(
                    "anthropic",
                    model,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                    purpose="ai_service",
                )

            # Parse JSON from content string
            try:
                parsed_content = json.loads(content)
                return {**parsed_content, "tokens_used": tokens_used}
            except json.JSONDecodeError:
                # If not valid JSON, return as-is
                return {"content": content, "tokens_used": tokens_used}

        # Call with retry strategy and circuit breaker
        return await self._anthropic_retry.execute_with_retry(_make_request)

    def _build_outline_prompt(
        self,
        document: Document,
        additional_requirements: str | None = None,
        *,
        source_pack: "SourcePack | None" = None,
    ) -> str:
        """Build prompt for outline generation.

        When a source pack is provided, the outline is planned around the
        available on-topic sources and given a per-section word budget so the
        section count is realistic for the target length and fully deliverable.
        With no pack, the prompt is byte-identical to the legacy behavior.
        """
        if source_pack is not None and source_pack.sources:
            return self._build_grounded_outline_prompt(
                document, additional_requirements, source_pack
            )
        prompt = f"""
Generate a detailed academic thesis outline for the following topic:

Topic: {document.topic}
Language: {document.language}
Target Pages: {document.target_pages}

Additional Requirements: {additional_requirements or 'None specified'}

CRITICAL: You must respond with ONLY a valid JSON object in this EXACT format:
{{
  "sections": [
    {{
      "title": "Introduction",
      "main_points": ["Overview of the topic", "Research objectives", "Thesis structure"],
      "subsections": ["Background", "Problem Statement", "Objectives"],
      "estimated_words": 400,
      "key_concepts": ["Topic Introduction", "Research Context"]
    }},
    {{
      "title": "Literature Review",
      "main_points": ["Previous research", "Theoretical framework", "Research gaps"],
      "subsections": ["Historical Context", "Current State", "Gaps"],
      "estimated_words": 800,
      "key_concepts": ["Literature Analysis", "Research Gaps"]
    }},
    {{
      "title": "Methodology",
      "main_points": ["Research design", "Data collection", "Analysis methods"],
      "subsections": ["Research Design", "Data Collection", "Analysis"],
      "estimated_words": 600,
      "key_concepts": ["Research Methods", "Data Analysis"]
    }},
    {{
      "title": "Results",
      "main_points": ["Key findings", "Data analysis", "Results interpretation"],
      "subsections": ["Main Findings", "Data Presentation", "Analysis"],
      "estimated_words": 800,
      "key_concepts": ["Research Results", "Data Findings"]
    }},
    {{
      "title": "Discussion",
      "main_points": ["Results interpretation", "Implications", "Limitations"],
      "subsections": ["Interpretation", "Implications", "Limitations"],
      "estimated_words": 600,
      "key_concepts": ["Results Discussion", "Research Implications"]
    }},
    {{
      "title": "Conclusion",
      "main_points": ["Summary", "Key findings", "Future research"],
      "subsections": ["Summary", "Contributions", "Future Work"],
      "estimated_words": 400,
      "key_concepts": ["Research Conclusion", "Future Directions"]
    }}
  ]
}}

Generate {max(3, min(10, document.target_pages // 10))} main sections appropriate for this topic.
Respond with ONLY the JSON object, no additional text or markdown formatting.
"""
        return prompt.strip()

    def _build_grounded_outline_prompt(
        self,
        document: Document,
        additional_requirements: str | None,
        source_pack: "SourcePack",
    ) -> str:
        """Outline prompt grounded in the upfront topic-locked source pack."""
        # ~250 words per page (matches cost_estimator.TOKENS_PER_PAGE ≈ 250 wpp).
        words_per_page = 250
        target_words = max(1, document.target_pages) * words_per_page
        n_sections = max(3, min(10, document.target_pages // 10))
        sources_block = source_pack.prompt_block()

        prompt = f"""
Generate a detailed academic thesis outline for the following topic:

Topic: {document.topic}
Language: {document.language}
Target Pages: {document.target_pages}

Additional Requirements: {additional_requirements or 'None specified'}

AVAILABLE SOURCES (plan the outline so every section can be supported by these):
{sources_block}

CRITICAL: You must respond with ONLY a valid JSON object in this EXACT format:
{{
  "sections": [
    {{
      "title": "Introduction",
      "main_points": ["Overview of the topic", "Research objectives"],
      "subsections": ["Background", "Problem Statement"],
      "estimated_words": 400,
      "key_concepts": ["Topic Introduction", "Research Context"]
    }},
    {{
      "title": "...",
      "main_points": ["..."],
      "subsections": ["..."],
      "estimated_words": 600,
      "key_concepts": ["..."]
    }}
  ]
}}

Requirements:
- Generate exactly {n_sections} main sections appropriate for this topic and
  grounded in the AVAILABLE SOURCES above (do not plan sections the sources
  cannot support).
- Set "estimated_words" per section so the totals sum to approximately
  {target_words} words (Target Pages × ~250 words/page).
- Each section must be distinct — do not repeat the same idea across sections.

Respond with ONLY the JSON object, no additional text or markdown formatting.
"""
        return prompt.strip()
