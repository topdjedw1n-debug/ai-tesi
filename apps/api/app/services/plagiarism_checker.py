"""
Plagiarism checker service using Copyscape API
Checks document uniqueness and plagiarism percentage
"""

import logging
from typing import Any

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


class PlagiarismChecker:
    """Check documents for plagiarism using Copyscape API"""

    def __init__(self) -> None:
        """Initialize plagiarism checker"""
        self.api_key = (
            settings.COPYSCAPE_API_KEY
            if hasattr(settings, "COPYSCAPE_API_KEY")
            else None
        )
        self.api_username = (
            settings.COPYSCAPE_USERNAME
            if hasattr(settings, "COPYSCAPE_USERNAME")
            else None
        )
        self.base_url = "https://www.copyscape.com/api"

    async def check_text(self, text: str, max_words: int = 1000) -> dict[str, Any]:
        """
        Check text for plagiarism using Copyscape API

        Args:
            text: Text to check
            max_words: Maximum words to check (default: 1000, Copyscape limit)

        Returns:
            Dictionary with plagiarism check results
        """
        if not self.api_key or not self.api_username:
            logger.warning("Copyscape API credentials not configured")
            return {
                "checked": False,
                "error": "Copyscape API not configured",
                "uniqueness_percentage": None,
            }

        try:
            # Truncate text if too long (Copyscape has limits)
            words = text.split()[:max_words]
            text_to_check = " ".join(words)

            # Prepare request
            params = {
                "u": self.api_username,
                "k": self.api_key,
                "o": "csearch",  # Text search
                "t": text_to_check,
                "e": "UTF-8",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(f"{self.base_url}/", params=params)
                response.raise_for_status()

            # Parse Copyscape response (XML format)
            import xml.etree.ElementTree as ET

            root = ET.fromstring(response.text)

            # Extract results
            results = []
            uniqueness = 100.0

            for result in root.findall(".//result"):
                url = result.find("url")
                title = result.find("title")
                words_found = result.find("words")
                minwords = result.find("minwords")

                if url is not None and words_found is not None:
                    results.append(
                        {
                            "url": url.text,
                            "title": title.text if title is not None else "",
                            "words_matched": int(words_found.text)
                            if words_found.text
                            else 0,
                            "min_words": int(minwords.text)
                            if minwords is not None and minwords.text
                            else 0,
                        }
                    )

            # Calculate uniqueness percentage
            # If matches found, reduce uniqueness based on matched words
            if results:
                total_words_checked = len(words)
                matched_words = sum(r["words_matched"] for r in results)
                if total_words_checked > 0:
                    uniqueness = max(
                        0.0,
                        100.0 - (matched_words / total_words_checked * 100),
                    )

            return {
                "checked": True,
                "uniqueness_percentage": round(uniqueness, 2),
                "matches_found": len(results),
                "matches": results,
                "text_length_words": len(words),
            }

        except httpx.HTTPError as e:
            logger.error(f"HTTP error checking plagiarism: {e}")
            return {
                "checked": False,
                "error": f"HTTP error: {str(e)}",
                "uniqueness_percentage": None,
            }
        except Exception as e:
            logger.error(f"Error checking plagiarism: {e}")
            return {
                "checked": False,
                "error": str(e),
                "uniqueness_percentage": None,
            }

    async def check_document_section(
        self, content: str, section_title: str
    ) -> dict[str, Any]:
        """
        Check a document section for plagiarism

        Args:
            content: Section content
            section_title: Section title for logging

        Returns:
            Dictionary with plagiarism check results
        """
        logger.info(f"Checking plagiarism for section: {section_title}")
        result = await self.check_text(content)
        result["section_title"] = section_title
        return result
