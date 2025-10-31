"""
Text humanization service
Paraphrases AI-generated text to make it sound more natural while preserving citations
"""

import logging

from app.core.config import settings
from app.services.ai_pipeline.prompt_builder import PromptBuilder

logger = logging.getLogger(__name__)


class Humanizer:
    """Humanize AI-generated text while preserving citations"""

    def __init__(self, temperature: float = 0.9):
        """
        Initialize humanizer

        Args:
            temperature: Temperature for paraphrasing (higher = more creative)
        """
        self.temperature = temperature

    async def humanize(
        self,
        text: str,
        provider: str,
        model: str,
        preserve_citations: bool = True
    ) -> str:
        """
        Humanize text while preserving citations

        Args:
            text: Original text to humanize
            provider: AI provider ("openai" or "anthropic")
            model: Model name
            preserve_citations: Whether to preserve citation markers

        Returns:
            Humanized text
        """
        try:
            # Extract citations before humanization
            from app.services.ai_pipeline.citation_formatter import CitationFormatter
            citations = CitationFormatter.extract_citations_from_text(text) if preserve_citations else []

            # Build humanization prompt
            prompt = PromptBuilder.build_humanization_prompt(text, preserve_citations)

            # Call AI provider with higher temperature
            humanized_text = await self._call_ai_provider(
                provider=provider,
                model=model,
                prompt=prompt,
                temperature=self.temperature
            )

            # Verify citations are preserved
            if preserve_citations and citations:
                preserved_count = 0
                for citation in citations:
                    if citation["original"] in humanized_text:
                        preserved_count += 1

                preservation_rate = preserved_count / len(citations) if citations else 1.0
                if preservation_rate < 0.8:  # Warn if <80% citations preserved
                    logger.warning(
                        f"Citation preservation rate: {preservation_rate:.2%}. "
                        f"Expected ≥80%."
                    )

            return humanized_text

        except Exception as e:
            logger.error(f"Error humanizing text: {e}")
            # Return original text on error
            return text

    async def _call_ai_provider(
        self,
        provider: str,
        model: str,
        prompt: str,
        temperature: float
    ) -> str:
        """Call AI provider for humanization"""
        if provider == "openai":
            return await self._call_openai(model, prompt, temperature)
        elif provider == "anthropic":
            return await self._call_anthropic(model, prompt, temperature)
        else:
            raise ValueError(f"Unsupported AI provider: {provider}")

    async def _call_openai(self, model: str, prompt: str, temperature: float) -> str:
        """Call OpenAI API for humanization"""
        try:
            import openai

            if not settings.OPENAI_API_KEY:
                raise ValueError("OpenAI API key not configured")

            client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

            response = await client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": "You are an expert at paraphrasing academic text while maintaining meaning and preserving citation markers."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=4000,
                temperature=temperature
            )

            return response.choices[0].message.content or ""

        except Exception as e:
            logger.error(f"OpenAI API error: {e}")
            raise

    async def _call_anthropic(self, model: str, prompt: str, temperature: float) -> str:
        """Call Anthropic API for humanization"""
        try:
            import anthropic

            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("Anthropic API key not configured")

            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)

            response = await client.messages.create(
                model=model,
                max_tokens=4000,
                temperature=temperature,
                system="You are an expert at paraphrasing academic text while maintaining meaning and preserving citation markers.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

