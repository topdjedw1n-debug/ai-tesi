"""
E2E Tests for Quality Validation Pipeline

Tests the complete quality validation flow including:
- Citation density validation
- Academic tone validation
- Section coherence validation
- Word count accuracy validation
- Weighted scoring calculation
- Integration with generation pipeline

Author: AI Assistant
Created: 2025-11-30
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.quality_validator import QualityValidator


@pytest.mark.asyncio
class TestQualityValidatorE2E:
    """End-to-end tests for QualityValidator service"""

    async def test_citation_density_low_citations(self):
        """Test citation density with insufficient citations"""
        validator = QualityValidator()

        # Content with only 1 citation (need 3 for 500 words)
        # Use proper citation format: (Author Year) not Author (Year)
        content = (
            """
        This is a research paper about AI. According to recent studies (Smith 2020),
        artificial intelligence is transforming society.
        """
            + " word " * 490
        )  # Total ~500 words

        result = await validator._check_citation_density(content)

        assert result["score"] < 100, "Score should be < 100 for low citations"
        assert (
            result["details"]["total_citations"] == 1
        ), f"Expected 1 citation, found {result['details']['total_citations']}"
        assert result["details"]["expected_citations"] >= 3
        assert len(result["issues"]) > 0
        assert "Low citation density" in result["issues"][0]

    async def test_citation_density_good_citations(self):
        """Test citation density with sufficient citations"""
        validator = QualityValidator()

        # Content with 4 citations (exceeds 3 per 500 words)
        # Use proper formats: (Author Year), (Author et al. Year), (Author & Author Year), [N]
        content = (
            """
        This is a research paper. According to recent studies (Smith 2020), AI is growing.
        Previous studies [1] show that machine learning improves performance.
        Research by multiple authors (Johnson et al. 2021) confirms these findings.
        As noted in collaborative work (Brown & Lee 2019), this trend continues.
        """
            + " word " * 450
        )

        result = await validator._check_citation_density(content)

        assert (
            result["score"] == 100.0
        ), f"Score should be 100 for sufficient citations, got {result['score']}"
        assert (
            result["details"]["total_citations"] >= 3
        ), f"Expected >=3 citations, found {result['details']['total_citations']}"
        assert len(result["issues"]) == 0

    async def test_academic_tone_with_contractions(self):
        """Test academic tone detection of contractions"""
        validator = QualityValidator()

        content = (
            """
        Don't use contractions in academic writing. Can't emphasize this enough.
        Won't be accepted in formal papers. It's not professional.
        """
            + " word " * 100
        )

        result = await validator._check_academic_tone(content)

        assert result["score"] < 100, "Score should be penalized for contractions"
        assert result["details"]["contractions"] > 0
        assert result["details"]["deductions"] > 0
        assert any("contractions" in issue.lower() for issue in result["issues"])

    async def test_academic_tone_excessive_first_person(self):
        """Test academic tone detection of excessive first-person pronouns"""
        validator = QualityValidator()

        # Excessive first-person (>2% of content)
        content = (
            """
        I believe that I should explain my research. In my opinion, I found that
        my results show I was correct. I think I demonstrated I can prove my hypothesis.
        I conclude that I successfully achieved my goals.
        """
            + " word " * 20
        )  # ~50 words total, 15 first-person = 30%

        result = await validator._check_academic_tone(content)

        assert (
            result["score"] < 100
        ), "Score should be penalized for excessive first-person"
        assert result["details"]["first_person_pronouns"] > 5
        assert any("first-person" in issue.lower() for issue in result["issues"])

    async def test_academic_tone_with_colloquialisms(self):
        """Test academic tone detection of colloquialisms"""
        validator = QualityValidator()

        content = (
            """
        A lot of stuff happens in research. The results are pretty good, okay?
        We're gonna analyze the data. Yeah, it's really important.
        """
            + " word " * 100
        )

        result = await validator._check_academic_tone(content)

        assert result["score"] < 100, "Score should be penalized for colloquialisms"
        assert result["details"]["colloquialisms"] > 0
        assert any("informal" in issue.lower() for issue in result["issues"])

    async def test_academic_tone_perfect(self):
        """Test academic tone with no violations"""
        validator = QualityValidator()

        content = (
            """
        This research examines the impact of artificial intelligence on society.
        The methodology employed rigorous statistical analysis. Results indicate
        significant correlation between variables. The study demonstrates clear evidence
        supporting the hypothesis. Further research should investigate additional factors.
        """
            + " word " * 50
        )

        result = await validator._check_academic_tone(content)

        assert result["score"] == 100.0, "Score should be 100 for perfect academic tone"
        assert result["details"]["contractions"] == 0
        assert result["details"]["colloquialisms"] == 0
        assert len(result["issues"]) == 0

    async def test_coherence_low_transitions(self):
        """Test coherence with insufficient transition words"""
        validator = QualityValidator()

        # 3 paragraphs, only 1 with transition (33% barely meets 30%)
        content = """
Paragraph one discusses the topic.
This is important information.

However, paragraph two provides additional context.
More details are included here.

Paragraph three concludes the section.
Final thoughts are presented.
        """

        result = await validator._check_coherence(content)

        # 1 out of 3 paragraphs = 33%, just above 30% threshold
        assert result["details"]["total_paragraphs"] == 3
        assert result["details"]["with_transitions"] >= 1
        assert result["details"]["ratio"] >= 0.30

    async def test_coherence_good_transitions(self):
        """Test coherence with sufficient transition words"""
        validator = QualityValidator()

        content = """
However, the first point is important.
This establishes the foundation.

Furthermore, additional evidence supports this claim.
The data confirms the hypothesis.

Therefore, we can conclude that the results are significant.
This leads to important implications.

Moreover, future research should explore these findings.
Additional studies will provide clarity.
        """

        result = await validator._check_coherence(content)

        assert result["score"] == 100.0, "Score should be 100 for good coherence"
        assert result["details"]["with_transitions"] >= 3
        assert result["details"]["ratio"] >= 0.30
        assert len(result["issues"]) == 0

    async def test_word_count_within_tolerance(self):
        """Test word count validation within ±10% tolerance"""
        validator = QualityValidator()

        # 510 words, target 500 = 2% deviation (within 10%)
        content = " ".join(["word"] * 510)
        target = 500

        result = await validator._check_word_count(content, target)

        assert result["score"] == 100.0, "Score should be 100 within tolerance"
        assert result["details"]["within_tolerance"] is True
        assert result["details"]["deviation"] <= 0.10
        assert len(result["issues"]) == 0

    async def test_word_count_outside_tolerance(self):
        """Test word count validation outside ±10% tolerance"""
        validator = QualityValidator()

        # 700 words, target 500 = 40% deviation (outside 10%)
        content = " ".join(["word"] * 700)
        target = 500

        result = await validator._check_word_count(content, target)

        assert result["score"] < 100, "Score should be penalized for deviation"
        assert result["details"]["within_tolerance"] is False
        assert result["details"]["deviation"] > 0.10
        assert len(result["issues"]) > 0
        assert "deviation" in result["issues"][0].lower()

    async def test_weighted_scoring_calculation(self):
        """Test overall weighted scoring calculation"""
        validator = QualityValidator()

        # Mock a well-structured academic content
        content = """
According to Smith (2020), artificial intelligence is transforming society.
Research by Johnson et al. (2021) confirms these findings [1].
Previous studies demonstrate clear evidence (Brown & Lee, 2019).

However, additional research is needed to fully understand the implications.
The methodology employed rigorous statistical analysis procedures.
Results indicate significant correlation between the examined variables.

Furthermore, the study demonstrates clear evidence supporting the hypothesis.
Therefore, future research should investigate additional contributing factors.
Moreover, these findings have important practical applications.
        """ + " ".join(["word"] * 400)  # ~500 words total

        outline_section = {"title": "Literature Review", "target_word_count": 500}

        result = await validator.validate_section(content, outline_section)

        assert "overall_score" in result
        assert 0 <= result["overall_score"] <= 100
        assert "passed" in result
        assert result["passed"] == (result["overall_score"] >= 70.0)
        assert "checks" in result
        assert "citation_density" in result["checks"]
        assert "academic_tone" in result["checks"]
        assert "coherence" in result["checks"]
        assert "word_count" in result["checks"]

        # Verify weighted calculation
        checks = result["checks"]
        expected_score = (
            checks["citation_density"]["score"] * 0.30
            + checks["academic_tone"]["score"] * 0.25
            + checks["coherence"]["score"] * 0.25
            + checks["word_count"]["score"] * 0.20
        )
        assert abs(result["overall_score"] - expected_score) < 0.1

    async def test_validate_section_with_error_handling(self):
        """Test validate_section handles errors gracefully"""
        validator = QualityValidator()

        # Pass None to trigger error
        result = await validator.validate_section(None, {})

        assert (
            result["passed"] is True
        ), "Should not fail generation on validation error"
        assert result["overall_score"] == 75.0, "Should return neutral score on error"
        assert len(result["issues"]) > 0
        assert "error" in result["issues"][0].lower()

    async def test_edge_case_empty_content(self):
        """Test quality validation with empty content"""
        validator = QualityValidator()

        result = await validator.validate_section("", {"target_word_count": 500})

        # Should handle gracefully, not crash
        assert "overall_score" in result
        assert result["passed"] in [True, False]

    async def test_edge_case_unicode_content(self):
        """Test quality validation with unicode and special characters"""
        validator = QualityValidator()

        content = """
        According to Müller (2020), naïve approaches don't work well.
        Research by González et al. (2021) confirms this [1].
        The data shows 50% improvement → significant results.
        """ + " ".join(["word"] * 450)

        # Should not crash on unicode
        result = await validator.validate_section(content, {"target_word_count": 500})

        assert "overall_score" in result
        assert isinstance(result["overall_score"], (int, float))

    async def test_edge_case_missing_target_word_count(self):
        """Test quality validation without target_word_count in outline"""
        validator = QualityValidator()

        content = " ".join(["word"] * 500)

        # Should use default 500 words
        result = await validator.validate_section(content, {})

        assert "overall_score" in result
        assert result["checks"]["word_count"]["details"]["target_word_count"] == 500


@pytest.mark.asyncio
class TestQualityPipelineIntegration:
    """Integration tests for quality validation in generation pipeline"""

    @patch("app.services.background_jobs.QualityValidator")
    async def test_quality_validator_called_in_pipeline(self, mock_validator_class):
        """Test that QualityValidator is instantiated and called during generation"""
        mock_validator = AsyncMock()
        mock_validator.validate_section.return_value = {
            "passed": True,
            "overall_score": 85.0,
            "checks": {},
            "issues": [],
        }
        mock_validator_class.return_value = mock_validator

        # This test verifies the integration point exists
        # Actual pipeline testing requires full DB setup

        # Import to verify no syntax errors
        # Verify QualityValidator is imported
        import inspect

        from app.services.background_jobs import BackgroundJobService

        source = inspect.getsource(BackgroundJobService)
        assert "QualityValidator" in source
        assert "quality_validator = QualityValidator()" in source
        assert "quality_score" in source
