"""
Section generator orchestrator
Integrates RAG, citations, and humanization for section generation
"""

import asyncio
import gc
import logging
from collections.abc import Callable
from typing import Any, TypeVar

from app.core.config import settings
from app.models.document import Document
from app.services.ai_pipeline.citation_formatter import CitationFormatter, CitationStyle
from app.services.ai_pipeline.humanizer import Humanizer
from app.services.ai_pipeline.prompt_builder import PromptBuilder
from app.services.ai_pipeline.rag_retriever import RAGRetriever, SourceDoc
from app.services.training_data_collector import TrainingDataCollector

logger = logging.getLogger(__name__)

# Type variable for generic retry function
T = TypeVar("T")


# ============================================================================
# RETRY MECHANISM - Task 3.1: Exponential Backoff
# ============================================================================
async def retry_with_backoff(
    func: Callable[..., Any],
    max_retries: int = 3,
    delays: list[int] | None = None,
    exceptions: tuple[type[Exception], ...] = (Exception,),
    operation_name: str = "AI call",
) -> Any:
    """
    Retry async function with exponential backoff on failure.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts (default: 3)
        delays: List of delays in seconds for each retry (default: [2, 4, 8])
        exceptions: Tuple of exception types to catch and retry (default: all exceptions)
        operation_name: Name of operation for logging (default: "AI call")

    Returns:
        Result from successful function call

    Raises:
        Last exception if all retries exhausted

    Example:
        >>> async def unstable_api_call():
        >>>     return await openai_client.create(...)
        >>> result = await retry_with_backoff(
        >>>     unstable_api_call,
        >>>     max_retries=3,
        >>>     delays=[2, 4, 8],
        >>>     exceptions=(Timeout, RateLimitError)
        >>> )
    """
    if delays is None:
        delays = [2, 4, 8]

    last_exception = None

    for attempt in range(max_retries):
        try:
            logger.debug(f"{operation_name}: Attempt {attempt + 1}/{max_retries}")
            result = await func()

            if attempt > 0:
                logger.info(
                    f"{operation_name}: Succeeded on attempt {attempt + 1}/{max_retries}"
                )

            return result

        except exceptions as e:
            last_exception = e
            exception_name = type(e).__name__

            if attempt < max_retries - 1:
                delay = delays[min(attempt, len(delays) - 1)]
                logger.warning(
                    f"{operation_name}: {exception_name} on attempt {attempt + 1}/{max_retries}. "
                    f"Retrying in {delay}s... Error: {str(e)[:100]}"
                )
                await asyncio.sleep(delay)
                continue
            else:
                logger.error(
                    f"{operation_name}: Failed after {max_retries} attempts. "
                    f"Last error: {exception_name}: {str(e)[:200]}"
                )
                raise

    # This should never be reached, but for type safety
    if last_exception:
        raise last_exception
    raise RuntimeError(
        f"{operation_name}: Retry logic error - no exception but no success"
    )


# ============================================================================
# SECTION GENERATOR CLASS
# ============================================================================


class SectionGenerator:
    """Generate academic sections with RAG, citations, and optional humanization"""

    def __init__(
        self,
        rag_retriever: RAGRetriever | None = None,
        citation_formatter: CitationFormatter | None = None,
        humanizer: Humanizer | None = None,
    ):
        """
        Initialize section generator

        Args:
            rag_retriever: RAG retriever instance (optional, creates default if None)
            citation_formatter: Citation formatter instance (optional, creates default if None)
            humanizer: Humanizer instance (optional, creates default if None)
        """
        self.rag_retriever = rag_retriever or RAGRetriever()
        self.citation_formatter = citation_formatter or CitationFormatter()
        self.humanizer = humanizer or Humanizer()
        self.prompt_builder = PromptBuilder()
        self.training_collector = TrainingDataCollector()

    async def generate_section(
        self,
        document: Document,
        section_title: str,
        section_index: int,
        provider: str,
        model: str,
        citation_style: CitationStyle = CitationStyle.APA,
        humanize: bool = False,
        context_sections: list[dict[str, Any]] | None = None,
        additional_requirements: str | None = None,
    ) -> dict[str, Any]:
        """
        Generate a section with RAG context, citations, and optional humanization

        Args:
            document: Document model instance
            section_title: Title of the section
            section_index: Index of the section
            provider: AI provider ("openai" or "anthropic")
            model: Model name
            citation_style: Citation style (APA, MLA, Chicago)
            humanize: Whether to humanize the output
            context_sections: Previously generated sections for context
            additional_requirements: Optional additional requirements

        Returns:
            Dictionary with section content, citations, and bibliography
        """
        try:
            # Step 1: Retrieve relevant sources using RAG from multiple APIs
            logger.info(f"Retrieving sources for section: {section_title}")
            query = f"{document.topic} {section_title}"
            source_docs = await self.rag_retriever.retrieve_sources(
                query=query, limit=20
            )

            # Step 2: Format sources for prompt
            source_texts = []
            for doc in source_docs:
                authors_str = ", ".join(doc.authors[:2])
                if len(doc.authors) > 2:
                    authors_str += " et al."
                source_texts.append(f"{doc.title} ({authors_str}, {doc.year})")

            # Step 3: Build prompt with RAG context
            prompt = self.prompt_builder.build_section_prompt(
                document=document,
                section_title=section_title,
                section_index=section_index,
                context_sections=context_sections,
                retrieved_sources=source_texts,
                additional_requirements=additional_requirements,
            )

            # Step 4: Generate section content using AI with automatic fallback
            logger.info(f"Generating section content: {section_title}")

            # Use fallback chain instead of single provider (Task 3.2)
            # Note: provider/model parameters are now ignored in favor of fallback chain
            # This ensures maximum reliability with automatic fallback
            section_content = await self._call_ai_with_fallback(
                prompt=prompt,
                language=str(document.language),
                purpose=f"Section: {section_title}",
            )

            # Store prompt for training data collection
            prompt_for_training = prompt

            # Step 5: Extract citations from generated text
            citations = self.citation_formatter.extract_citations_from_text(
                section_content
            )

            # Step 6: Build bibliography from retrieved sources
            bibliography = []
            citation_map: dict[str, SourceDoc] = {}

            # Map citations to source documents using scoring algorithm
            for citation in citations:
                best_match: SourceDoc | None = None
                best_score = 0.0

                # Score each source document for this citation
                for doc in source_docs:
                    score = self._score_citation_match(citation, doc)
                    if score > best_score:
                        best_score = score
                        best_match = doc

                # Add to map if found good match (score > 0)
                if best_match and best_score > 0:
                    citation_key = citation["original"]
                    if citation_key not in citation_map:
                        citation_map[citation_key] = best_match
                        logger.debug(
                            f"Matched citation '{citation_key}' to '{best_match.title}' "
                            f"(score: {best_score:.1f})"
                        )

            # Generate bibliography entries
            for doc in source_docs:
                if doc in citation_map.values():
                    reference = self.citation_formatter.format_reference(
                        doc.to_source_document(), style=citation_style
                    )
                    bibliography.append(reference)

            # Step 7: Humanize if requested
            if humanize:
                logger.info(f"Humanizing section: {section_title}")
                section_content = await self.humanizer.humanize(
                    text=section_content,
                    provider=provider,
                    model=model,
                    preserve_citations=True,
                )

            result = {
                "section_title": section_title,
                "section_index": section_index,
                "content": section_content,
                "citations": citations,
                "bibliography": bibliography,
                "sources_used": len(source_docs),
                "humanized": humanize,
            }

            # Collect training data (async, non-blocking)
            asyncio.create_task(
                self.training_collector.collect_generation_sample(
                    document_id=int(document.id),
                    section_title=section_title,
                    prompt=prompt_for_training,
                    generated_content=section_content,
                    context={
                        "sources": source_texts,
                        "context_sections": [
                            s.get("title") for s in (context_sections or [])
                        ],
                    },
                    metadata={
                        "provider": provider,
                        "model": model,
                        "citation_style": citation_style.value
                        if hasattr(citation_style, "value")
                        else str(citation_style),
                        "humanized": humanize,
                    },
                )
            )

            # Memory cleanup after section generation
            self._cleanup_memory()

            return result

        except Exception as e:
            logger.error(f"Error generating section: {e}")
            # Cleanup memory even on error
            self._cleanup_memory()
            raise

    def _score_citation_match(
        self, citation: dict[str, Any], source: SourceDoc
    ) -> float:
        """
        Score how well a citation matches a source document

        Args:
            citation: Citation dict with 'year', 'authors', 'original' keys
            source: Source document to match against

        Returns:
            Match score (higher = better match, 0 = no match)

        Scoring algorithm:
            - Exact year match: +50 points
            - Author last name match: +30 points per matching author
            - Title word overlap: +20 points
        """
        score = 0.0

        # 1. Year matching (most reliable indicator)
        if citation.get("year") and str(source.year) == str(citation["year"]):
            score += 50.0

        # 2. Author matching (check last names)
        citation_authors = citation.get("authors", [])
        if citation_authors and source.authors:
            for citation_author in citation_authors:
                # Extract last name (last word in author string)
                citation_last_name = citation_author.strip().split()[-1].lower()

                for source_author in source.authors:
                    source_last_name = source_author.strip().split()[-1].lower()

                    if (
                        citation_last_name in source_last_name
                        or source_last_name in citation_last_name
                    ):
                        score += 30.0
                        break  # Count each citation author only once

        # 3. Title similarity (check for word overlap)
        citation_text = citation.get("original", "").lower()
        title_words = set(source.title.lower().split())

        # Remove common words
        stop_words = {
            "the",
            "a",
            "an",
            "and",
            "or",
            "of",
            "in",
            "on",
            "at",
            "to",
            "for",
        }
        title_words = title_words - stop_words

        matching_words = sum(1 for word in title_words if word in citation_text)
        if matching_words > 0:
            score += 20.0

        return score

    def _cleanup_memory(self) -> None:
        """
        Clean up memory after section generation
        Forces garbage collection and logs memory usage
        """
        try:
            # Get memory usage before cleanup
            import os

            import psutil

            process = psutil.Process(os.getpid())
            mem_before = process.memory_info().rss / 1024 / 1024  # MB

            # Clear internal caches if any
            # Force garbage collection
            collected = gc.collect()

            # Get memory usage after cleanup
            mem_after = process.memory_info().rss / 1024 / 1024  # MB
            mem_freed = mem_before - mem_after

            logger.debug(
                f"Memory cleanup: {collected} objects collected, "
                f"freed {mem_freed:.2f} MB (before: {mem_before:.2f} MB, after: {mem_after:.2f} MB)"
            )

        except ImportError:
            # psutil not available, use basic gc
            collected = gc.collect()
            logger.debug(
                f"Memory cleanup: {collected} objects collected (psutil not available)"
            )
        except Exception as e:
            logger.warning(f"Error during memory cleanup: {e}")
            # Still try basic gc
            gc.collect()

    async def _call_ai_provider(
        self, provider: str, model: str, prompt: str, language: str = "en"
    ) -> str:
        """
        Call AI provider for section generation (DEPRECATED - use _call_ai_with_fallback instead)

        This method is kept for backward compatibility but should not be used directly.
        Use _call_ai_with_fallback() for automatic provider fallback.
        """
        if provider == "openai":
            return await self._call_openai(model, prompt, language)
        elif provider == "anthropic":
            return await self._call_anthropic(model, prompt, language)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

    async def _call_ai_with_fallback(
        self,
        prompt: str,
        language: str = "en",
        purpose: str = "generation",
    ) -> str:
        """
        Call AI with automatic fallback chain on failure.

        Tries providers in order from AI_FALLBACK_CHAIN config until one succeeds.
        Each provider already has retry logic (_call_openai/_call_anthropic).

        Default fallback chain:
        1. OpenAI GPT-4 (best quality)
        2. OpenAI GPT-3.5 Turbo (cheaper fallback)
        3. Anthropic Claude 3.5 Sonnet (different provider)

        Args:
            prompt: The prompt to send to AI
            language: Language code for system prompt (default: 'en')
            purpose: Description of what this call is for (for logging)

        Returns:
            Generated text from first successful provider

        Raises:
            AllProvidersFailedError: If all providers in chain fail

        Example:
            >>> text = await self._call_ai_with_fallback(
            >>>     prompt="Generate introduction...",
            >>>     language="en",
            >>>     purpose="Introduction section"
            >>> )
        """
        from app.core.exceptions import AllProvidersFailedError

        # Check if fallback is disabled
        if not settings.AI_ENABLE_FALLBACK:
            logger.info(f"Fallback disabled, using default provider for {purpose}")
            # Use first provider from chain as default
            provider, model = settings.AI_FALLBACK_CHAIN_LIST[0]
            return (
                await self._call_openai(model, prompt, language)
                if provider == "openai"
                else await self._call_anthropic(model, prompt, language)
            )

        # Try each provider in fallback chain
        fallback_chain = settings.AI_FALLBACK_CHAIN_LIST
        last_error: Exception | None = None

        logger.info(
            f"Starting AI call with fallback for {purpose}. "
            f"Chain: {' → '.join(f'{p}:{m}' for p, m in fallback_chain)}"
        )

        for index, (provider, model) in enumerate(fallback_chain):
            try:
                logger.info(
                    f"Attempting provider {index + 1}/{len(fallback_chain)}: "
                    f"{provider}/{model} for {purpose}"
                )

                if provider == "openai":
                    result = await self._call_openai(model, prompt, language)
                elif provider == "anthropic":
                    result = await self._call_anthropic(model, prompt, language)
                else:
                    logger.warning(f"Unknown provider '{provider}', skipping")
                    continue

                logger.info(
                    f"✅ Success with {provider}/{model} for {purpose} "
                    f"(attempt {index + 1}/{len(fallback_chain)})"
                )
                return result

            except Exception as e:
                last_error = e
                exception_name = type(e).__name__
                logger.warning(
                    f"❌ Failed {provider}/{model} for {purpose}: "
                    f"{exception_name}: {str(e)[:200]}"
                )

                # If this is not the last provider, continue to next
                if index < len(fallback_chain) - 1:
                    logger.info("Falling back to next provider in chain...")
                    continue
                else:
                    logger.error(
                        f"All {len(fallback_chain)} providers failed for {purpose}. "
                        f"Last error: {exception_name}"
                    )

        # All providers failed
        error_detail = (
            f"All AI providers failed for {purpose}. "
            f"Tried {len(fallback_chain)} providers. "
            f"Last error: {type(last_error).__name__}: {str(last_error)[:200]}"
            if last_error
            else "Unknown error"
        )
        raise AllProvidersFailedError(error_detail)

    async def _call_openai(self, model: str, prompt: str, language: str = "en") -> str:
        """
        Call OpenAI API with automatic retry on transient failures

        Retries on:
        - Timeout errors
        - Rate limit errors
        - API connection errors
        - General API errors

        Uses exponential backoff: 2s, 4s, 8s delays
        """
        try:
            import openai

            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")

            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            # Get language-specific system prompt
            system_prompt = PromptBuilder.get_system_prompt(language)

            # Define retryable exceptions (specific to OpenAI SDK)
            retryable_exceptions = (
                openai.APITimeoutError,
                openai.RateLimitError,
                openai.APIConnectionError,
                openai.APIError,
            )

            # Inner function for retry wrapper
            async def _make_openai_call() -> str:
                response = await client.chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "system",
                            "content": system_prompt,
                        },
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=4000,
                    temperature=0.7,
                )
                return response.choices[0].message.content or ""

            # Use retry mechanism with exponential backoff
            return await retry_with_backoff(
                func=_make_openai_call,
                max_retries=settings.AI_MAX_RETRIES,
                delays=settings.AI_RETRY_DELAYS_LIST,
                exceptions=retryable_exceptions,
                operation_name=f"OpenAI {model}",
            )

        except Exception as e:
            logger.error(f"OpenAI API error (all retries exhausted): {e}")
            raise

    async def _call_anthropic(
        self, model: str, prompt: str, language: str = "en"
    ) -> str:
        """
        Call Anthropic API with automatic retry on transient failures

        Retries on:
        - Timeout errors
        - Rate limit errors
        - API connection errors
        - General API errors

        Uses exponential backoff: 2s, 4s, 8s delays
        """
        try:
            import anthropic

            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("Anthropic API key not configured")

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            # Get language-specific system prompt
            system_prompt = PromptBuilder.get_system_prompt(language)

            # Define retryable exceptions (specific to Anthropic SDK)
            retryable_exceptions = (
                anthropic.APITimeoutError,
                anthropic.RateLimitError,
                anthropic.APIConnectionError,
                anthropic.APIError,
            )

            # Inner function for retry wrapper
            async def _make_anthropic_call() -> str:
                response = await client.messages.create(  # type: ignore[attr-defined]
                    model=model,
                    max_tokens=4000,
                    temperature=0.7,
                    system=system_prompt,
                    messages=[{"role": "user", "content": prompt}],
                )
                return response.content[0].text

            # Use retry mechanism with exponential backoff
            return await retry_with_backoff(
                func=_make_anthropic_call,
                max_retries=settings.AI_MAX_RETRIES,
                delays=settings.AI_RETRY_DELAYS_LIST,
                exceptions=retryable_exceptions,
                operation_name=f"Anthropic {model}",
            )

        except Exception as e:
            logger.error(f"Anthropic API error (all retries exhausted): {e}")
            raise
