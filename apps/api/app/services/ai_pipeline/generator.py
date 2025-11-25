"""
Section generator orchestrator
Integrates RAG, citations, and humanization for section generation
"""

import asyncio
import gc
import logging
from typing import Any

from app.core.config import settings
from app.models.document import Document
from app.services.ai_pipeline.citation_formatter import CitationFormatter, CitationStyle
from app.services.ai_pipeline.humanizer import Humanizer
from app.services.ai_pipeline.prompt_builder import PromptBuilder
from app.services.ai_pipeline.rag_retriever import RAGRetriever, SourceDoc
from app.services.training_data_collector import TrainingDataCollector

logger = logging.getLogger(__name__)


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

            # Step 4: Generate section content using AI
            logger.info(f"Generating section content: {section_title}")
            section_content = await self._call_ai_provider(
                provider=provider, model=model, prompt=prompt
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

            # Map citations to source documents
            for citation in citations:
                # Try to match citation to retrieved source
                for doc in source_docs:
                    # Match by year and author
                    if doc.year == citation["year"]:
                        if any(
                            author.lower() in citation["authors"][0].lower()
                            for author in doc.authors
                        ):
                            citation_key = citation["original"]
                            if citation_key not in citation_map:
                                citation_map[citation_key] = doc
                            break

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
                    document_id=document.id,
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

    async def _call_ai_provider(self, provider: str, model: str, prompt: str) -> str:
        """Call AI provider for section generation"""
        if provider == "openai":
            return await self._call_openai(model, prompt)
        elif provider == "anthropic":
            return await self._call_anthropic(model, prompt)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

    async def _call_openai(self, model: str, prompt: str) -> str:
        """Call OpenAI API"""
        try:
            import openai

            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")

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

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def _call_anthropic(self, model: str, prompt: str) -> str:
        """Call Anthropic API"""
        try:
            import anthropic

            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("Anthropic API key not configured")

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            response = await client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=0.7,
                system="You are an expert academic writer specializing in thesis and research paper generation.",
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise
