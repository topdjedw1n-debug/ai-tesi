"""
AI Detection checker service using GPTZero and Originality.ai APIs
Detects AI-generated content probability to ensure human-like quality
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class AIDetectionChecker:
    """Check text for AI-generated content probability"""

    def __init__(self):
        """Initialize AI detection checker with GPTZero primary, Originality fallback"""
        # GPTZero API (primary)
        self.gptzero_api_url = "https://api.gptzero.me/v2/predict/text"
        self.gptzero_api_key = getattr(settings, "GPTZERO_API_KEY", None)

        # Originality.ai API (fallback)
        self.originality_api_url = "https://api.originality.ai/api/v1/scan/ai"
        self.originality_api_key = getattr(settings, "ORIGINALITY_AI_API_KEY", None)

        # Configuration
        self.enabled = getattr(settings, "AI_DETECTION_ENABLED", True)
        self.timeout = 30.0

    async def check_text(self, text: str) -> dict[str, Any]:
        """
        Check text for AI detection probability

        Args:
            text: Text to check for AI-generated content

        Returns:
            Dictionary with AI detection results:
            {
                "checked": bool,
                "ai_probability": float (0-100),
                "human_probability": float (0-100),
                "provider": str ("gptzero" | "originality" | "none"),
                "error": str | None
            }
        """
        if not self.enabled:
            logger.debug("AI detection disabled, skipping check")
            return {
                "checked": False,
                "error": "AI detection is disabled",
                "provider": "none",
            }

        # Try GPTZero first (primary provider)
        if self.gptzero_api_key:
            result = await self._check_with_gptzero(text)
            if result["checked"]:
                return result
            logger.warning(
                f"GPTZero failed: {result.get('error', 'Unknown')}. "
                "Trying Originality.ai fallback..."
            )

        # Fallback to Originality.ai
        if self.originality_api_key:
            result = await self._check_with_originality(text)
            if result["checked"]:
                return result
            logger.warning(
                f"Originality.ai also failed: {result.get('error', 'Unknown')}"
            )

        # Both providers failed
        logger.error("All AI detection providers failed")
        return {
            "checked": False,
            "error": "All AI detection providers unavailable",
            "provider": "none",
        }

    async def _check_with_gptzero(self, text: str) -> dict[str, Any]:
        """
        Check text using GPTZero API

        Args:
            text: Text to analyze

        Returns:
            Detection results from GPTZero
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.gptzero_api_url,
                    json={"document": text},
                    headers={"x-api-key": self.gptzero_api_key},
                )
                response.raise_for_status()
                result = response.json()

            # Parse GPTZero response
            # completely_generated_prob: 0-1 float (probability document is AI-generated)
            documents = result.get("documents", [])
            if not documents:
                return {
                    "checked": False,
                    "error": "No documents in GPTZero response",
                    "provider": "gptzero",
                }

            ai_prob = documents[0].get("completely_generated_prob", 0) * 100

            logger.info(
                f"GPTZero check completed: {ai_prob:.1f}% AI-generated probability"
            )

            return {
                "checked": True,
                "ai_probability": ai_prob,
                "human_probability": 100 - ai_prob,
                "provider": "gptzero",
                "error": None,
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"GPTZero API HTTP error: {e.response.status_code} - {e}")
            return {
                "checked": False,
                "error": f"HTTP {e.response.status_code}",
                "provider": "gptzero",
            }
        except Exception as e:
            logger.error(f"GPTZero API error: {e}")
            return {
                "checked": False,
                "error": str(e),
                "provider": "gptzero",
            }

    async def _check_with_originality(self, text: str) -> dict[str, Any]:
        """
        Check text using Originality.ai API as fallback

        Args:
            text: Text to analyze

        Returns:
            Detection results from Originality.ai
        """
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.originality_api_url,
                    json={"content": text},
                    headers={"X-OAI-API-KEY": self.originality_api_key},
                )
                response.raise_for_status()
                result = response.json()

            # Parse Originality.ai response
            # score.ai: 0-1 float (AI detection score)
            score = result.get("score", {})
            ai_score = score.get("ai", 0) * 100

            logger.info(
                f"Originality.ai check completed: {ai_score:.1f}% AI-generated probability"
            )

            return {
                "checked": True,
                "ai_probability": ai_score,
                "human_probability": 100 - ai_score,
                "provider": "originality",
                "error": None,
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"Originality.ai API HTTP error: {e.response.status_code} - {e}")
            return {
                "checked": False,
                "error": f"HTTP {e.response.status_code}",
                "provider": "originality",
            }
        except Exception as e:
            logger.error(f"Originality.ai API error: {e}")
            return {
                "checked": False,
                "error": str(e),
                "provider": "originality",
            }
