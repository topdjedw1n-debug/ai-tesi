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

    MAX_WORDS_PER_REQUEST = 1000

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
        Check all text for plagiarism using bounded Copyscape requests.

        Args:
            text: Text to check
            max_words: Maximum words per request. Values above Copyscape's
                1000-word limit are capped; the full text is still checked.

        Returns:
            Aggregated plagiarism result. Any unchecked chunk makes the whole
            result unchecked so a partial provider response cannot look clean.
        """
        words = text.split()
        chunk_size = min(max_words, self.MAX_WORDS_PER_REQUEST)
        if chunk_size <= 0:
            return {
                "checked": False,
                "error": "Plagiarism chunk size must be greater than zero",
                "uniqueness_percentage": None,
                "text_length_words": len(words),
                "chunks_total": 0,
                "chunks_checked": 0,
                "chunk_results": [],
                "matches_found": 0,
                "matches": [],
            }

        word_chunks = [
            words[start : start + chunk_size]
            for start in range(0, len(words), chunk_size)
        ]
        # Preserve the previous configured-provider behavior for empty input:
        # send one empty request and let Copyscape accept or reject it.
        if not word_chunks:
            word_chunks = [[]]

        if not self.api_key or not self.api_username:
            logger.warning("Copyscape API credentials not configured")
            return {
                "checked": False,
                "error": "Copyscape API not configured",
                "uniqueness_percentage": None,
                "text_length_words": len(words),
                "chunks_total": len(word_chunks),
                "chunks_checked": 0,
                "chunk_results": [],
                "matches_found": 0,
                "matches": [],
            }

        chunk_results: list[dict[str, Any]] = []
        all_matches: list[dict[str, Any]] = []
        word_offset = 0

        for chunk_index, chunk_words in enumerate(word_chunks, start=1):
            result = await self._check_chunk(" ".join(chunk_words))
            word_start = word_offset + 1 if chunk_words else 0
            word_end = word_offset + len(chunk_words)

            # A provider response that claims success without a score is not
            # complete enough to contribute to a green section result.
            if result.get("checked") and result.get("uniqueness_percentage") is None:
                result = {
                    **result,
                    "checked": False,
                    "error": "Copyscape returned no uniqueness score",
                }

            chunk_matches = [
                {
                    **match,
                    "chunk_index": chunk_index,
                    "word_start": word_start,
                    "word_end": word_end,
                }
                for match in result.get("matches", [])
            ]
            all_matches.extend(chunk_matches)
            chunk_results.append(
                {
                    **result,
                    "matches": chunk_matches,
                    "matches_found": len(chunk_matches),
                    "chunk_index": chunk_index,
                    "word_start": word_start,
                    "word_end": word_end,
                    "text_length_words": len(chunk_words),
                }
            )
            word_offset = word_end

        checked_chunks = [result for result in chunk_results if result["checked"]]
        failed_chunks = [result for result in chunk_results if not result["checked"]]
        checked_uniqueness = [
            float(result["uniqueness_percentage"]) for result in checked_chunks
        ]
        partial_uniqueness = min(checked_uniqueness) if checked_uniqueness else None

        aggregated: dict[str, Any] = {
            "checked": not failed_chunks,
            # The worst chunk wins. A highly copied passage must not be diluted
            # by unrelated clean chunks elsewhere in a long section.
            "uniqueness_percentage": (
                round(partial_uniqueness, 2)
                if not failed_chunks and partial_uniqueness is not None
                else None
            ),
            "matches_found": len(all_matches),
            "matches": all_matches,
            "text_length_words": len(words),
            "chunks_total": len(chunk_results),
            "chunks_checked": len(checked_chunks),
            "chunk_results": chunk_results,
        }

        if failed_chunks:
            failed_numbers = [result["chunk_index"] for result in failed_chunks]
            failure_details = "; ".join(
                f"chunk {result['chunk_index']}: "
                f"{result.get('error', 'plagiarism check unavailable')}"
                for result in failed_chunks
            )
            aggregated.update(
                {
                    "error": (
                        "Plagiarism check incomplete: "
                        f"{len(failed_chunks)} of {len(chunk_results)} chunks "
                        f"unchecked ({failure_details})"
                    ),
                    "partial_uniqueness_percentage": (
                        round(partial_uniqueness, 2)
                        if partial_uniqueness is not None
                        else None
                    ),
                    "failed_chunks": failed_numbers,
                }
            )

        return aggregated

    async def _check_chunk(self, text: str) -> dict[str, Any]:
        """Check one Copyscape-sized text chunk."""
        try:
            # Defensive cap: callers should use check_text(), but no request
            # may exceed Copyscape's documented 1000-word boundary.
            words = text.split()[: self.MAX_WORDS_PER_REQUEST]
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
            error_text = (error_el.text or "").strip() if error_el is not None else ""
            if error_text:
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

            results: list[dict[str, Any]] = []
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
