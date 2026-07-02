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

            # Prepare request. Copyscape requires POST for text searches —
            # with GET the "t" parameter is rejected ("Please enter some
            # text…") and the old code silently read that as 0 matches.
            params = {
                "u": self.api_username,
                "k": self.api_key,
                "o": "csearch",  # Text search
                "t": text_to_check,
                "e": "UTF-8",
            }

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(f"{self.base_url}/", data=params)
                response.raise_for_status()

            # Parse Copyscape response (XML format)
            import xml.etree.ElementTree as ET

            root = ET.fromstring(response.text)

            # API-level errors (bad credentials, no credits, rejected input)
            # come back as HTTP 200 with an <error> element. Absence of
            # <result> elements must NOT be read as "no matches" here —
            # that is exactly the fail-open that masked a dead checker.
            error_el = root.find(".//error")
            if error_el is not None and (error_el.text or "").strip():
                error_text = error_el.text.strip()
                logger.warning(f"Copyscape API error: {error_text}")
                return {
                    "checked": False,
                    "error": f"Copyscape API error: {error_text}",
                    "uniqueness_percentage": None,
                }

            # Extract results. Real csearch responses carry the match size
            # in <minwordsmatched> (plus <allwordsmatched> when full
            # comparisons are enabled) — NOT in <words>/<minwords>, which
            # the old parser expected and therefore dropped every result.
            def _int_text(el: Any) -> int:
                return int(el.text) if el is not None and el.text else 0

            results = []
            uniqueness = 100.0

            for result in root.findall(".//result"):
                url = result.find("url")
                title = result.find("title")
                matched = max(
                    _int_text(result.find("minwordsmatched")),
                    _int_text(result.find("allwordsmatched")),
                    _int_text(result.find("words")),  # legacy shape
                )
                if url is not None:
                    results.append(
                        {
                            "url": url.text,
                            "title": title.text if title is not None else "",
                            "words_matched": matched,
                        }
                    )

            # Uniqueness = share of the query NOT found in the single best
            # match. Summing across results would over-count: the same
            # copied passage appears on many pages at once.
            querywords = _int_text(root.find(".//querywords")) or len(words)
            if results and querywords > 0:
                best_match = max(r["words_matched"] for r in results)
                uniqueness = max(0.0, 100.0 - (best_match / querywords * 100))

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
