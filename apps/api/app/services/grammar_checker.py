"""
Grammar checker service using LanguageTool API
Checks grammar, spelling, and style issues in generated text
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class GrammarChecker:
    """Check grammar and spelling using LanguageTool API"""

    def __init__(self):
        """Initialize grammar checker"""
        # LanguageTool can be self-hosted or use public API
        self.api_url = getattr(
            settings, "LANGUAGETOOL_API_URL", "https://api.languagetool.org/v2"
        )
        self.api_key = getattr(settings, "LANGUAGETOOL_API_KEY", None)
        self.enabled = getattr(settings, "LANGUAGETOOL_ENABLED", True)

    async def check_text(self, text: str, language: str = "en-US") -> dict[str, Any]:
        """
        Check text for grammar and spelling errors

        Args:
            text: Text to check
            language: Language code (default: en-US)

        Returns:
            Dictionary with grammar check results
        """
        if not self.enabled:
            logger.debug("LanguageTool disabled, skipping grammar check")
            return {
                "checked": False,
                "error": "LanguageTool is disabled",
                "matches": [],
            }

        try:
            # Prepare request
            data = {
                "text": text,
                "language": language,
            }

            headers = {}
            if self.api_key:
                headers["Authorization"] = f"Bearer {self.api_key}"

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    f"{self.api_url}/check",
                    data=data,
                    headers=headers,
                )
                response.raise_for_status()
                result = response.json()

            # Parse LanguageTool response
            matches = []
            for match in result.get("matches", []):
                matches.append(
                    {
                        "message": match.get("message", ""),
                        "short_message": match.get("shortMessage", ""),
                        "offset": match.get("offset", 0),
                        "length": match.get("length", 0),
                        "rule_id": match.get("rule", {}).get("id", ""),
                        "rule_description": match.get("rule", {}).get(
                            "description", ""
                        ),
                        "category": match.get("rule", {})
                        .get("category", {})
                        .get("id", ""),
                        "replacements": [
                            r.get("value", "") for r in match.get("replacements", [])
                        ],
                        "context": match.get("context", {}).get("text", ""),
                        "context_offset": match.get("context", {}).get("offset", 0),
                    }
                )

            # Calculate statistics
            total_errors = len(matches)
            error_types = {}
            for match in matches:
                category = match.get("category", "unknown")
                error_types[category] = error_types.get(category, 0) + 1

            return {
                "checked": True,
                "language": language,
                "total_errors": total_errors,
                "matches": matches,
                "error_types": error_types,
                "text_length": len(text),
            }

        except httpx.HTTPError as e:
            logger.warning(f"HTTP error checking grammar: {e}")
            return {
                "checked": False,
                "error": f"HTTP error: {str(e)}",
                "matches": [],
            }
        except Exception as e:
            logger.error(f"Error checking grammar: {e}")
            return {
                "checked": False,
                "error": str(e),
                "matches": [],
            }

    async def check_document_section(
        self, content: str, section_title: str, language: str = "en-US"
    ) -> dict[str, Any]:
        """
        Check a document section for grammar errors

        Args:
            content: Section content
            section_title: Section title for logging
            language: Language code

        Returns:
            Dictionary with grammar check results
        """
        logger.info(f"Checking grammar for section: {section_title}")
        result = await self.check_text(content, language)
        result["section_title"] = section_title
        return result
