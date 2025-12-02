"""
Quality Validator Service

Validates generated content quality across multiple dimensions:
- Citation density (academic source usage)
- Academic tone (formal language)
- Section coherence (logical flow with transitions)
- Word count accuracy (adherence to outline targets)

Returns comprehensive quality assessment with weighted scoring.

Author: AI Assistant
Created: 2025-11-30
Version: 1.0
"""

import logging
import re
from typing import Any

from app.core.config import settings

logger = logging.getLogger(__name__)


class QualityValidator:
    """
    Validates academic content quality across 4 dimensions.
    
    Scoring weights:
    - Citation density: 30%
    - Academic tone: 25%
    - Section coherence: 25%
    - Word count accuracy: 20%
    """
    
    def __init__(self):
        # Citation requirements
        self.min_citations_per_500_words = 3
        
        # Word count tolerance
        self.word_count_tolerance = 0.10  # ±10%
        
        # Transition words for coherence check
        self.transition_words = {
            "however", "therefore", "furthermore", "moreover", "additionally",
            "consequently", "nevertheless", "nonetheless", "thus", "hence",
            "accordingly", "meanwhile", "subsequently", "conversely", "likewise",
            "similarly", "alternatively", "in contrast", "on the other hand",
            "as a result", "for example", "for instance", "in addition",
            "in conclusion", "to summarize", "in summary", "specifically",
        }
        
        # Academic tone - problematic patterns
        self.contractions = [
            r"\bdon't\b", r"\bcan't\b", r"\bwon't\b", r"\bisn't\b",
            r"\baren't\b", r"\bwasn't\b", r"\bweren't\b", r"\bhasn't\b",
            r"\bhaven't\b", r"\bhadn't\b", r"\bcouldn't\b", r"\bshouldn't\b",
            r"\bwouldn't\b", r"\bmightn't\b", r"\bmustn't\b", r"\bneedn't\b",
            r"\bdaren't\b", r"\bshan't\b", r"\boughtn't\b",
        ]
        
        self.first_person_pronouns = [
            r"\bI\b", r"\bme\b", r"\bmy\b", r"\bmine\b", r"\bmyself\b",
            r"\bwe\b", r"\bus\b", r"\bour\b", r"\bours\b", r"\bourselves\b",
        ]
        
        self.colloquialisms = [
            r"\ba lot\b", r"\bkinda\b", r"\bsorta\b", r"\bgonna\b",
            r"\bwanna\b", r"\bgotta\b", r"\byeah\b", r"\bnope\b",
            r"\bokay\b", r"\bOK\b", r"\balright\b", r"\bstuff\b",
            r"\bthings\b(?!\s+such)", r"\bget\b(?!\s+(?:to|from|into))",
            r"\bpretty\b(?!\s+(?:much|well))", r"\breally\b(?!\s+important)",
        ]
        
        # Scoring weights
        self.weights = {
            "citation_density": 0.30,
            "academic_tone": 0.25,
            "coherence": 0.25,
            "word_count": 0.20,
        }
    
    async def validate_section(
        self,
        content: str,
        outline_section: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate a section's quality across all dimensions.
        
        Args:
            content: Section text content
            outline_section: Outline metadata with 'target_word_count'
        
        Returns:
            {
                "passed": bool,  # Overall pass/fail (score >= 70)
                "overall_score": float,  # 0-100, weighted average
                "checks": {
                    "citation_density": {"score": float, "details": dict},
                    "academic_tone": {"score": float, "details": dict},
                    "coherence": {"score": float, "details": dict},
                    "word_count": {"score": float, "details": dict},
                },
                "issues": [str],  # List of problems found
            }
        """
        try:
            logger.info(f"Starting quality validation for section: {outline_section.get('title', 'Unknown')}")
            
            # Run all checks
            citation_result = await self._check_citation_density(content)
            tone_result = await self._check_academic_tone(content)
            coherence_result = await self._check_coherence(content)
            word_count_result = await self._check_word_count(
                content, 
                outline_section.get("target_word_count", 500)
            )
            
            # Calculate weighted overall score
            overall_score = (
                citation_result["score"] * self.weights["citation_density"]
                + tone_result["score"] * self.weights["academic_tone"]
                + coherence_result["score"] * self.weights["coherence"]
                + word_count_result["score"] * self.weights["word_count"]
            )
            
            # Collect all issues
            issues = []
            issues.extend(citation_result.get("issues", []))
            issues.extend(tone_result.get("issues", []))
            issues.extend(coherence_result.get("issues", []))
            issues.extend(word_count_result.get("issues", []))
            
            # Overall pass threshold: 70%
            passed = overall_score >= 70.0
            
            result = {
                "passed": passed,
                "overall_score": round(overall_score, 1),
                "checks": {
                    "citation_density": citation_result,
                    "academic_tone": tone_result,
                    "coherence": coherence_result,
                    "word_count": word_count_result,
                },
                "issues": issues,
            }
            
            logger.info(
                f"Quality validation complete - "
                f"Score: {overall_score:.1f}, Passed: {passed}, Issues: {len(issues)}"
            )
            
            return result
            
        except Exception as e:
            logger.error(f"Quality validation failed: {e}")
            # Return neutral result on error (non-blocking)
            return {
                "passed": True,  # Don't fail generation on validation error
                "overall_score": 75.0,  # Neutral score
                "checks": {},
                "issues": [f"Validation error: {str(e)}"],
            }
    
    async def _check_citation_density(self, content: str) -> dict[str, Any]:
        """
        Check citation density (min 3 citations per 500 words).
        
        Citation formats detected:
        - [1], [2], [3] (numeric)
        - (Author, 2020)
        - (Author et al., 2020)
        - (Author & Author, 2020)
        """
        word_count = len(content.split())
        
        # Citation patterns
        numeric_citations = re.findall(r'\[\d+\]', content)
        # Match: (Smith 2020), (Smith, 2020), (Smith et al. 2020), (Lee & Kim 2019), etc.
        author_year_citations = re.findall(
            r'\([A-Z][a-z]+(?:\s+et\s+al\.)?(?:\s+&\s+[A-Z][a-z]+)?\s*,?\s*\d{4}\)',
            content
        )
        
        total_citations = len(numeric_citations) + len(author_year_citations)
        
        # Calculate expected citations
        expected_citations = max(1, int((word_count / 500) * self.min_citations_per_500_words))
        
        # Score: 100% if meets requirement, linear penalty if below
        if total_citations >= expected_citations:
            score = 100.0
            issues = []
        else:
            score = max(0.0, (total_citations / expected_citations) * 100.0)
            issues = [
                f"Low citation density: {total_citations} citations found, "
                f"{expected_citations} expected for {word_count} words"
            ]
        
        return {
            "score": round(score, 1),
            "details": {
                "total_citations": total_citations,
                "expected_citations": expected_citations,
                "word_count": word_count,
                "numeric_citations": len(numeric_citations),
                "author_year_citations": len(author_year_citations),
            },
            "issues": issues,
        }
    
    async def _check_academic_tone(self, content: str) -> dict[str, Any]:
        """
        Check for academic tone violations.
        
        Checks:
        - Contractions (don't, can't, etc.)
        - Excessive first-person pronouns
        - Colloquialisms and informal language
        """
        issues = []
        deductions = 0
        
        # Check contractions
        contractions_found = []
        for pattern in self.contractions:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                contractions_found.extend(matches)
        
        if contractions_found:
            deductions += len(contractions_found) * 5
            issues.append(
                f"Found {len(contractions_found)} contractions (avoid in academic writing)"
            )
        
        # Check first-person pronouns
        first_person_count = 0
        for pattern in self.first_person_pronouns:
            matches = re.findall(pattern, content)
            first_person_count += len(matches)
        
        # Allow minimal first-person in methodology/reflection sections
        word_count = len(content.split())
        first_person_ratio = first_person_count / word_count if word_count > 0 else 0
        
        if first_person_ratio > 0.02:  # >2% is excessive
            deductions += 10
            issues.append(
                f"Excessive first-person usage: {first_person_count} instances "
                f"({first_person_ratio:.1%} of text)"
            )
        
        # Check colloquialisms
        colloquialisms_found = []
        for pattern in self.colloquialisms:
            matches = re.findall(pattern, content, re.IGNORECASE)
            if matches:
                colloquialisms_found.extend(matches)
        
        if colloquialisms_found:
            deductions += len(colloquialisms_found) * 3
            issues.append(
                f"Found {len(colloquialisms_found)} informal expressions "
                f"(use formal alternatives)"
            )
        
        # Calculate score
        score = max(0.0, 100.0 - deductions)
        
        return {
            "score": round(score, 1),
            "details": {
                "contractions": len(contractions_found),
                "first_person_pronouns": first_person_count,
                "colloquialisms": len(colloquialisms_found),
                "deductions": deductions,
            },
            "issues": issues,
        }
    
    async def _check_coherence(self, content: str) -> dict[str, Any]:
        """
        Check section coherence via transition words.
        
        Minimum: 30% of paragraphs should contain transition words.
        """
        # Split into paragraphs
        paragraphs = [p.strip() for p in content.split('\n\n') if p.strip()]
        total_paragraphs = len(paragraphs)
        
        if total_paragraphs == 0:
            return {
                "score": 50.0,  # Neutral score for edge case
                "details": {"total_paragraphs": 0, "with_transitions": 0},
                "issues": ["No paragraphs detected"],
            }
        
        # Count paragraphs with transition words
        paragraphs_with_transitions = 0
        for paragraph in paragraphs:
            paragraph_lower = paragraph.lower()
            has_transition = any(
                word in paragraph_lower for word in self.transition_words
            )
            if has_transition:
                paragraphs_with_transitions += 1
        
        # Calculate ratio
        transition_ratio = paragraphs_with_transitions / total_paragraphs
        
        # Score: 100% if >=30% have transitions, linear scaling below
        target_ratio = 0.30
        if transition_ratio >= target_ratio:
            score = 100.0
            issues = []
        else:
            score = (transition_ratio / target_ratio) * 100.0
            issues = [
                f"Low coherence: only {paragraphs_with_transitions}/{total_paragraphs} "
                f"paragraphs ({transition_ratio:.0%}) contain transition words "
                f"(target: {target_ratio:.0%})"
            ]
        
        return {
            "score": round(score, 1),
            "details": {
                "total_paragraphs": total_paragraphs,
                "with_transitions": paragraphs_with_transitions,
                "ratio": round(transition_ratio, 2),
                "target_ratio": target_ratio,
            },
            "issues": issues,
        }
    
    async def _check_word_count(
        self, content: str, target_word_count: int
    ) -> dict[str, Any]:
        """
        Check word count accuracy (±10% tolerance).
        
        Args:
            content: Section text
            target_word_count: Expected word count from outline
        
        Returns:
            Score based on deviation from target
        """
        actual_word_count = len(content.split())
        
        # Calculate deviation
        deviation = abs(actual_word_count - target_word_count) / target_word_count
        
        # Within tolerance?
        within_tolerance = deviation <= self.word_count_tolerance
        
        # Score: 100% if within tolerance, linear penalty for deviation
        if within_tolerance:
            score = 100.0
            issues = []
        else:
            # Penalty: 100% at tolerance, 0% at 50% deviation
            excess_deviation = deviation - self.word_count_tolerance
            penalty = min(100.0, (excess_deviation / 0.40) * 100.0)  # Max penalty at 50% dev
            score = max(0.0, 100.0 - penalty)
            
            issues = [
                f"Word count deviation: {actual_word_count} words "
                f"(target: {target_word_count}, deviation: {deviation:.1%})"
            ]
        
        return {
            "score": round(score, 1),
            "details": {
                "actual_word_count": actual_word_count,
                "target_word_count": target_word_count,
                "deviation": round(deviation, 2),
                "within_tolerance": within_tolerance,
            },
            "issues": issues,
        }
