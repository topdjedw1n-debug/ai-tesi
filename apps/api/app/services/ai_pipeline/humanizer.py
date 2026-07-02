"""
Text humanization service
Paraphrases AI-generated text to make it sound more natural while preserving citations
"""

import logging
import re
from typing import TYPE_CHECKING, Any

from app.core.config import settings
from app.services.ai_pipeline.prompt_builder import PromptBuilder

if TYPE_CHECKING:
    from app.services.cost_estimator import UsageTracker

logger = logging.getLogger(__name__)

# Per-attempt style directives for multi-pass humanization. Claude 4+/5 and
# gpt-5 reject the temperature param, so the old "progressive temperature"
# ladder silently sent IDENTICAL requests on those models (doc-10: repeat
# passes could only regress to the model's default — most detectable — style).
# Varying the instruction is the knob that still works on every model.
#
# MEASURED 03.07.2026 (doc 12, gpt-4 self-rescue): the aggressive v1
# directives ("aggressively vary sentence length...") RAISED GPTZero
# 56.4 -> 96.7 on the first pass — instructed "unusualness" reads as MORE
# AI-like, not less. Directives are now deliberately mild; the plain prompt
# (variant 0) is the doc-9-proven behavior.
STYLE_DIRECTIVES = [
    "",
    "",
    (
        "- Where it reads naturally, prefer slightly simpler wording over "
        "polished formulations\n"
    ),
    (
        "- You may merge or split an occasional sentence where a careful "
        "human editor would\n"
    ),
]

ENGLISH_STOPWORDS = {
    "the",
    "and",
    "or",
    "of",
    "to",
    "in",
    "for",
    "on",
    "with",
    "as",
    "by",
    "at",
    "from",
    "that",
    "this",
    "these",
    "those",
    "is",
    "are",
    "was",
    "were",
    "be",
    "been",
    "being",
    "it",
    "its",
    "an",
    "a",
}


def _english_stopword_ratio(text: str) -> float:
    words = re.findall(r"[A-Za-z]+", text.lower())
    if len(words) < 40:
        return 0.0
    count = sum(1 for word in words if word in ENGLISH_STOPWORDS)
    return count / len(words) if words else 0.0


class Humanizer:
    """Humanize AI-generated text while preserving citations"""

    def __init__(
        self,
        temperature: float = 0.9,
        usage_tracker: "UsageTracker | None" = None,
    ):
        """
        Initialize humanizer

        Args:
            temperature: Temperature for paraphrasing (higher = more creative)
            usage_tracker: When set, every provider call records its real
                response.usage here (covers humanize_multi_pass too)
        """
        self.temperature = temperature
        self.usage_tracker = usage_tracker

    async def humanize(
        self,
        text: str,
        provider: str,
        model: str,
        preserve_citations: bool = True,
        language: str = "en",
        style_variant: int = 0,
    ) -> str:
        """
        Humanize text while preserving citations

        Args:
            text: Original text to humanize
            provider: AI provider ("openai" or "anthropic")
            model: Model name
            preserve_citations: Whether to preserve citation markers
            language: Target language code for the output
            style_variant: Index into STYLE_DIRECTIVES (multi-pass sends a
                different directive each attempt; clamped to the last one)

        Returns:
            Humanized text
        """
        try:
            # Cross-model override: when configured, humanize with a fixed
            # provider/model instead of the writer's (same-model paraphrase
            # RAISES detector scores — doc-10). Resolved here so every caller
            # (single-pass, multi-pass, quality gates) gets it.
            if settings.HUMANIZER_PROVIDER and settings.HUMANIZER_MODEL:
                if (provider, model) != (
                    settings.HUMANIZER_PROVIDER,
                    settings.HUMANIZER_MODEL,
                ):
                    logger.info(
                        f"Humanizer override: {provider}/{model} -> "
                        f"{settings.HUMANIZER_PROVIDER}/{settings.HUMANIZER_MODEL}"
                    )
                provider = settings.HUMANIZER_PROVIDER
                model = settings.HUMANIZER_MODEL

            # Extract citations before humanization
            from app.services.ai_pipeline.citation_formatter import CitationFormatter

            citations = (
                CitationFormatter.extract_citations_from_text(text)
                if preserve_citations
                else []
            )

            # Build humanization prompt
            directive = STYLE_DIRECTIVES[
                min(max(style_variant, 0), len(STYLE_DIRECTIVES) - 1)
            ]
            prompt = PromptBuilder.build_humanization_prompt(
                text, preserve_citations, language, style_directive=directive
            )

            # Call AI provider with higher temperature
            humanized_text = await self._call_ai_provider(
                provider=provider,
                model=model,
                prompt=prompt,
                temperature=self.temperature,
            )

            # Language drift check (only for non-English targets)
            if language != "en":
                english_ratio = _english_stopword_ratio(humanized_text)
                if english_ratio >= 0.12:
                    logger.warning(
                        "Humanization language drift detected "
                        f"(english_ratio={english_ratio:.2f}). Returning original text."
                    )
                    return text

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
                        cit["original"]
                        for cit in citations
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

            request_kwargs: dict[str, Any] = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are an expert at paraphrasing academic text while maintaining meaning and preserving citation markers.",
                    },
                    {"role": "user", "content": prompt},
                ],
            }
            if model.startswith("gpt-5"):
                # gpt-5 family: max_tokens is rejected (400) — use
                # max_completion_tokens (covers reasoning tokens too, hence the
                # higher cap); temperature is not supported.
                request_kwargs["max_completion_tokens"] = 8000
            else:
                request_kwargs["max_tokens"] = 4000
                request_kwargs["temperature"] = temperature

            response = await client.chat.completions.create(**request_kwargs)

            if self.usage_tracker is not None and response.usage:
                self.usage_tracker.add(
                    "openai",
                    model,
                    response.usage.prompt_tokens or 0,
                    response.usage.completion_tokens or 0,
                    purpose="humanization",
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

            request_kwargs: dict[str, Any] = {
                "model": model,
                "max_tokens": 4000,
                "system": "You are an expert at paraphrasing academic text while maintaining meaning and preserving citation markers.",
                "messages": [{"role": "user", "content": prompt}],
            }
            # Claude 4+/5 models reject sampling params with a 400; only the
            # legacy claude-3 family still accepts temperature.
            if model.startswith("claude-3"):
                request_kwargs["temperature"] = temperature

            response = await client.messages.create(  # type: ignore[attr-defined]
                **request_kwargs
            )

            if self.usage_tracker is not None:
                self.usage_tracker.add(
                    "anthropic",
                    model,
                    response.usage.input_tokens,
                    response.usage.output_tokens,
                    purpose="humanization",
                )
            from app.utils.anthropic_helpers import response_text

            return response_text(response)

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
        language: str = "en",
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
            language: Target language code for the output

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

            # Vary BOTH knobs per attempt: temperature (only honored by
            # models that still accept it) and the style directive (works
            # everywhere — the only real variation on Claude 4+/5 / gpt-5).
            temp = temperatures[min(attempt, len(temperatures) - 1)]
            self.temperature = temp
            logger.info(
                f"Re-humanizing with temperature={temp}, "
                f"style_variant={attempt + 1} (attempt {attempt + 1}/{max_attempts})"
            )

            current_text = await self.humanize(
                text=current_text,
                provider=provider,
                model=model,
                preserve_citations=preserve_citations,
                language=language,
                style_variant=attempt + 1,
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
