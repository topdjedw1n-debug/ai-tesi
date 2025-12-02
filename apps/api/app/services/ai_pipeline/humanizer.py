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
        self, text: str, provider: str, model: str, preserve_citations: bool = True
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

            citations = (
                CitationFormatter.extract_citations_from_text(text)
                if preserve_citations
                else []
            )

            # Build humanization prompt
            prompt = PromptBuilder.build_humanization_prompt(text, preserve_citations)

            # Call AI provider with higher temperature
            humanized_text = await self._call_ai_provider(
                provider=provider,
                model=model,
                prompt=prompt,
                temperature=self.temperature,
            )

            # Verify citations are preserved
            if preserve_citations and citations:
                preserved_count = 0
                for citation in citations:
                    if citation["original"] in humanized_text:
                        preserved_count += 1

                preservation_rate = (
                    preserved_count / len(citations) if citations else 1.0
                )
                if preservation_rate < 0.8:  # Reject if <80% citations preserved
                    logger.error(
                        f"Citation preservation failed: {preservation_rate:.2%} "
                        f"(expected ≥80%). Returning original text to preserve citations."
                    )
                    # Log which citations were lost for debugging
                    lost_citations = [
                        cit["original"] for cit in citations 
                        if cit["original"] not in humanized_text
                    ]
                    logger.debug(f"Lost citations: {lost_citations}")
                    
                    # SAFE: Return original text instead of broken humanized version
                    return text
                else:
                    logger.info(
                        f"Citations preserved successfully: {preservation_rate:.2%}"
                    )

            return humanized_text

        except Exception as e:
            logger.error(f"Error humanizing text: {e}")
            # Return original text on error
            return text

    async def _call_ai_provider(
        self, provider: str, model: str, prompt: str, temperature: float
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
                    {
                        "role": "system",
                        "content": "You are an expert at paraphrasing academic text while maintaining meaning and preserving citation markers.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=4000,
                temperature=temperature,
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
                messages=[{"role": "user", "content": prompt}],
            )

            return response.content[0].text

        except Exception as e:
            logger.error(f"Anthropic API error: {e}")
            raise

    async def humanize_multi_pass(
        self,
        text: str,
        provider: str,
        model: str,
        target_ai_score: float = 50.0,
        max_attempts: int = 2,
        preserve_citations: bool = True,
    ) -> tuple[str, float]:
        """
        Multi-pass humanization to achieve target AI detection score

        Iteratively humanizes text with increasing temperature until
        AI detection score drops below target threshold.

        Args:
            text: Original text to humanize
            provider: AI provider ("openai" or "anthropic")
            model: Model name
            target_ai_score: Target AI detection score (default: 50.0%)
            max_attempts: Max humanization attempts (default: 2)
            preserve_citations: Whether to preserve citation markers

        Returns:
            Tuple of (humanized_text, final_ai_score)
        """
        from app.services.ai_detection_checker import AIDetectionChecker

        ai_checker = AIDetectionChecker()
        current_text = text
        temperatures = [0.9, 1.0, 1.1, 1.2]  # Progressive increase

        for attempt in range(max_attempts):
            # Check current AI score
            detection_result = await ai_checker.check_text(current_text)

            if not detection_result["checked"]:
                logger.warning(
                    f"AI detection failed on attempt {attempt + 1}: "
                    f"{detection_result.get('error', 'Unknown')}. Using text as-is."
                )
                break

            current_ai_score = detection_result["ai_probability"]
            provider_used = detection_result.get("provider", "unknown")
            logger.info(
                f"Humanization attempt {attempt + 1}/{max_attempts}: "
                f"AI score = {current_ai_score:.1f}% (provider: {provider_used})"
            )

            # Check if target achieved
            if current_ai_score <= target_ai_score:
                logger.info(
                    f"✅ Target AI score achieved: {current_ai_score:.1f}% <= {target_ai_score:.1f}%"
                )
                return current_text, current_ai_score

            # Humanize with progressive temperature
            temp = temperatures[min(attempt, len(temperatures) - 1)]
            self.temperature = temp
            logger.info(
                f"Re-humanizing with temperature={temp} (attempt {attempt + 1}/{max_attempts})"
            )

            current_text = await self.humanize(
                text=current_text,
                provider=provider,
                model=model,
                preserve_citations=preserve_citations,
            )

        # Max attempts reached - check final score
        final_detection = await ai_checker.check_text(current_text)
        final_score = (
            final_detection.get("ai_probability", 100.0)
            if final_detection["checked"]
            else 100.0
        )

        logger.warning(
            f"⚠️ Max humanization attempts ({max_attempts}) reached. "
            f"Final AI score: {final_score:.1f}%"
        )

        return current_text, final_score
