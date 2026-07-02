"""
Cost estimation service for AI document generation
Calculates estimated costs based on provider, model, and document parameters
"""

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Token pricing per 1M tokens (as of 2024)
# Input tokens (prompt)
PRICING_INPUT = {
    "openai": {
        "gpt-4": 30.0,  # $30 per 1M input tokens
        "gpt-4-turbo": 10.0,  # $10 per 1M input tokens
        "gpt-3.5-turbo": 0.5,  # $0.5 per 1M input tokens
        "gpt-5.5": 5.0,  # $5 per 1M input tokens
    },
    "anthropic": {
        "claude-3-5-sonnet-20241022": 3.0,  # $3 per 1M input tokens
        "claude-3-opus-20240229": 15.0,  # $15 per 1M input tokens
        "claude-opus-4-8": 5.0,  # $5 per 1M input tokens
        # Sonnet 5 intro pricing through 2026-08-31 ($2/$10), then $3/$15 —
        # update both dicts after that date so job costs match the invoice.
        "claude-sonnet-5": 2.0,
        "claude-haiku-4-5-20251001": 1.0,  # $1 per 1M input tokens
    },
}

# Output tokens (completion)
PRICING_OUTPUT = {
    "openai": {
        "gpt-4": 60.0,  # $60 per 1M output tokens
        "gpt-4-turbo": 30.0,  # $30 per 1M output tokens
        "gpt-3.5-turbo": 1.5,  # $1.5 per 1M output tokens
        "gpt-5.5": 30.0,  # $30 per 1M output tokens
    },
    "anthropic": {
        "claude-3-5-sonnet-20241022": 15.0,  # $15 per 1M output tokens
        "claude-3-opus-20240229": 75.0,  # $75 per 1M output tokens
        "claude-opus-4-8": 25.0,  # $25 per 1M output tokens
        "claude-sonnet-5": 10.0,  # intro through 2026-08-31, then $15
        "claude-haiku-4-5-20251001": 5.0,  # $5 per 1M output tokens
    },
}

# Average tokens per page (approximately 250 words per page, ~4 chars per token)
TOKENS_PER_PAGE = 1000  # ~1000 tokens per page
# Average ratio: ~70% input (prompt + context), ~30% output (generated content)
INPUT_RATIO = 0.7
OUTPUT_RATIO = 0.3


class CostEstimator:
    """Estimate costs for AI document generation"""

    @staticmethod
    def estimate_document_cost(
        provider: str,
        model: str,
        target_pages: int,
        include_rag: bool = True,
        include_humanization: bool = False,
    ) -> dict[str, Any]:
        """
        Estimate cost for full document generation

        Args:
            provider: AI provider ("openai" or "anthropic")
            model: Model name
            target_pages: Target number of pages
            include_rag: Whether RAG is enabled (adds ~20% to input tokens)
            include_humanization: Whether humanization is enabled (adds ~50% to output tokens)

        Returns:
            Dictionary with cost breakdown
        """
        try:
            # Get pricing for model
            input_price = PRICING_INPUT.get(provider, {}).get(model)
            output_price = PRICING_OUTPUT.get(provider, {}).get(model)

            if not input_price or not output_price:
                logger.warning(
                    f"Unknown pricing for {provider}/{model}, using defaults"
                )
                # Use GPT-4 defaults as fallback
                input_price = 30.0
                output_price = 60.0

            # Estimate tokens needed
            base_input_tokens = target_pages * TOKENS_PER_PAGE * INPUT_RATIO
            base_output_tokens = target_pages * TOKENS_PER_PAGE * OUTPUT_RATIO

            # Adjust for RAG (more input tokens for context)
            if include_rag:
                base_input_tokens = int(base_input_tokens * 1.2)

            # Adjust for humanization (more output tokens)
            if include_humanization:
                base_output_tokens = int(base_output_tokens * 1.5)

            # Calculate costs
            input_cost = (base_input_tokens / 1_000_000) * input_price
            output_cost = (base_output_tokens / 1_000_000) * output_price
            total_cost = input_cost + output_cost

            # Add margin for safety (20% buffer)
            estimated_total = total_cost * 1.2

            return {
                "provider": provider,
                "model": model,
                "target_pages": target_pages,
                "estimated_input_tokens": int(base_input_tokens),
                "estimated_output_tokens": int(base_output_tokens),
                "estimated_total_tokens": int(base_input_tokens + base_output_tokens),
                "input_cost_usd": round(input_cost, 4),
                "output_cost_usd": round(output_cost, 4),
                "base_cost_usd": round(total_cost, 4),
                "estimated_cost_usd": round(estimated_total, 4),
                "currency": "USD",
                "includes_rag": include_rag,
                "includes_humanization": include_humanization,
            }

        except Exception as e:
            logger.error(f"Error estimating cost: {e}")
            # Return safe default
            return {
                "provider": provider,
                "model": model,
                "target_pages": target_pages,
                "estimated_cost_usd": 0.0,
                "error": str(e),
            }

    @staticmethod
    def estimate_section_cost(
        provider: str,
        model: str,
        section_pages: float = 1.0,
        include_rag: bool = True,
    ) -> dict[str, Any]:
        """
        Estimate cost for single section generation

        Args:
            provider: AI provider
            model: Model name
            section_pages: Estimated pages for this section
            include_rag: Whether RAG is enabled

        Returns:
            Dictionary with cost breakdown
        """
        return CostEstimator.estimate_document_cost(
            provider=provider,
            model=model,
            target_pages=int(section_pages * 10),  # Round to 1 decimal
            include_rag=include_rag,
            include_humanization=False,
        )

    @staticmethod
    def get_model_pricing(provider: str, model: str) -> dict[str, float] | None:
        """
        Get pricing information for a specific model

        Args:
            provider: AI provider
            model: Model name

        Returns:
            Dictionary with input_price and output_price per 1M tokens, or None if unknown
        """
        input_price = PRICING_INPUT.get(provider, {}).get(model)
        output_price = PRICING_OUTPUT.get(provider, {}).get(model)

        if input_price is None or output_price is None:
            return None

        return {
            "input_price_per_1m": input_price,
            "output_price_per_1m": output_price,
        }


class UsageTracker:
    """
    Accumulates real token usage across every LLM call of one generation run
    (outline, sections, humanization passes, reviewer panel, claim verifier).

    Thread the same instance through the services' constructors; each
    provider call records its response.usage here. Totals are written to
    AIGenerationJob.total_tokens / cost_cents (absolute values, so
    incremental writes stay idempotent and a crashed job keeps honest
    partial numbers).
    """

    def __init__(self) -> None:
        # (provider, model) -> {"input_tokens": int, "output_tokens": int}
        self._by_model: dict[tuple[str, str], dict[str, int]] = {}

    def add(
        self,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        purpose: str = "",
    ) -> None:
        key = (provider or "unknown", model or "unknown")
        bucket = self._by_model.setdefault(key, {"input_tokens": 0, "output_tokens": 0})
        bucket["input_tokens"] += max(int(input_tokens or 0), 0)
        bucket["output_tokens"] += max(int(output_tokens or 0), 0)
        if purpose:
            logger.debug(
                f"Usage recorded ({purpose}): {key[0]}/{key[1]} "
                f"+{input_tokens} in / +{output_tokens} out"
            )

    @property
    def total_tokens(self) -> int:
        return sum(
            bucket["input_tokens"] + bucket["output_tokens"]
            for bucket in self._by_model.values()
        )

    def snapshot(self) -> int:
        """Current total, for computing per-section deltas."""
        return self.total_tokens

    def cost_usd_cents(self) -> int:
        """Real cost in USD cents from the per-model input/output split."""
        total_usd = 0.0
        for (provider, model), bucket in self._by_model.items():
            input_price = PRICING_INPUT.get(provider, {}).get(model)
            output_price = PRICING_OUTPUT.get(provider, {}).get(model)
            if input_price is None or output_price is None:
                logger.warning(
                    f"Unknown pricing for {provider}/{model}, using gpt-4 defaults"
                )
                input_price, output_price = 30.0, 60.0
            total_usd += (bucket["input_tokens"] / 1_000_000) * input_price
            total_usd += (bucket["output_tokens"] / 1_000_000) * output_price
        return round(total_usd * 100)
