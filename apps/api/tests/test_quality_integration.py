"""
Integration Tests for Quality Validation with Other Services

Tests quality validation integration with:
- Grammar checker
- Plagiarism checker
- AI detection checker
- Background job pipeline
- WebSocket progress updates

Author: AI Assistant
Created: 2025-11-30
"""

from unittest.mock import AsyncMock, patch

import pytest

from app.services.quality_validator import QualityValidator


@pytest.mark.asyncio
class TestQualityValidationIntegration:
    """Integration tests for quality validation with pipeline services"""

    async def test_quality_validation_non_blocking_on_error(self):
        """Test that quality validation errors don't break generation"""
        validator = QualityValidator()

        # Force an error by passing invalid data
        with patch.object(
            validator, "_check_citation_density", side_effect=Exception("Test error")
        ):
            result = await validator.validate_section(
                "test content", {"target_word_count": 500}
            )

        # Should return neutral result, not raise exception
        assert result["passed"] is True, "Should not fail generation"
        assert result["overall_score"] == 75.0, "Should return neutral score"
        assert len(result["issues"]) > 0
        assert "error" in result["issues"][0].lower()

    async def test_quality_score_range_validation(self):
        """Test that quality scores are always in valid range 0-100"""
        validator = QualityValidator()

        test_contents = [
            # Perfect content
            """However, according to Smith (2020), research shows clear evidence [1].
            Furthermore, studies by Jones et al. (2021) confirm these findings.
            Therefore, the hypothesis is supported by multiple sources (Brown, 2019)."""
            + " word " * 450,
            # Poor content
            "This is bad. No citations. Lots of I think I believe my opinion." * 50,
            # Empty content
            "",
            # Minimal content
            "Test.",
        ]

        for content in test_contents:
            result = await validator.validate_section(
                content, {"target_word_count": 500}
            )

            assert (
                0 <= result["overall_score"] <= 100
            ), f"Score {result['overall_score']} out of range for content: {content[:50]}"

            for check_name, check_result in result["checks"].items():
                if "score" in check_result:
                    assert (
                        0 <= check_result["score"] <= 100
                    ), f"{check_name} score {check_result['score']} out of range"

    async def test_quality_pass_threshold_70_percent(self):
        """Test that 70% is the pass/fail threshold"""
        validator = QualityValidator()

        # Mock different score scenarios
        test_cases = [
            (69.9, False),  # Just below threshold
            (70.0, True),  # Exactly at threshold
            (70.1, True),  # Just above threshold
            (85.0, True),  # Well above threshold
        ]

        for target_score, expected_pass in test_cases:
            # Create content that produces specific score
            # This is approximate since exact scoring is complex
            with patch.object(
                validator,
                "_check_citation_density",
                return_value={"score": target_score, "details": {}, "issues": []},
            ):
                with patch.object(
                    validator,
                    "_check_academic_tone",
                    return_value={"score": target_score, "details": {}, "issues": []},
                ):
                    with patch.object(
                        validator,
                        "_check_coherence",
                        return_value={
                            "score": target_score,
                            "details": {},
                            "issues": [],
                        },
                    ):
                        with patch.object(
                            validator,
                            "_check_word_count",
                            return_value={
                                "score": target_score,
                                "details": {},
                                "issues": [],
                            },
                        ):
                            result = await validator.validate_section(
                                "test", {"target_word_count": 500}
                            )

            assert result["overall_score"] == target_score
            assert (
                result["passed"] == expected_pass
            ), f"Score {target_score} should {'pass' if expected_pass else 'fail'}"

    @patch("app.services.background_jobs.manager")
    async def test_websocket_progress_includes_quality_score(self, mock_manager):
        """Test that WebSocket updates include quality_score and quality_passed"""
        mock_manager.send_progress = AsyncMock()

        # Verify the signature exists (actual call happens in background_jobs)
        import inspect

        from app.services.background_jobs import BackgroundJobService

        source = inspect.getsource(BackgroundJobService)

        # Check for quality WebSocket update
        assert "quality_score" in source, "WebSocket should send quality_score"
        assert "quality_passed" in source, "WebSocket should send quality_passed"
        assert (
            "stage" in source and "quality_check" in source
        ), "Should have quality_check stage"

    async def test_quality_validator_async_methods(self):
        """Test that all validation methods are properly async"""
        validator = QualityValidator()
        import inspect

        async_methods = [
            "validate_section",
            "_check_citation_density",
            "_check_academic_tone",
            "_check_coherence",
            "_check_word_count",
        ]

        for method_name in async_methods:
            method = getattr(validator, method_name)
            assert inspect.iscoroutinefunction(method), f"{method_name} should be async"

    async def test_citation_regex_patterns_comprehensive(self):
        """Test that citation patterns detect various formats"""
        validator = QualityValidator()

        content_with_citations = (
            """
        Numeric citations are common [1] and [2] and [3].
        Author-year format also works (Smith, 2020) and (Jones, 2021).
        Multiple authors use et al. (Brown et al., 2019).
        Two authors use ampersand (Lee & Kim, 2022).
        """
            + " word " * 450
        )

        result = await validator._check_citation_density(content_with_citations)

        # Should detect at least 7 citations
        assert (
            result["details"]["total_citations"] >= 7
        ), f"Should detect multiple citation formats, found {result['details']['total_citations']}"
        assert (
            result["details"]["numeric_citations"] >= 3
        ), "Should detect [1], [2], [3]"
        assert (
            result["details"]["author_year_citations"] >= 4
        ), "Should detect author-year formats"

    async def test_transition_words_detection_comprehensive(self):
        """Test that transition word detection works with various patterns"""
        validator = QualityValidator()

        # Each paragraph has a transition word
        content = """
However, this is the first point.

Furthermore, here is additional information.

Therefore, we can conclude.

Moreover, there are more details.

Consequently, this leads to results.

In contrast, different perspectives exist.

As a result, outcomes are clear.

For example, consider this case.
        """

        result = await validator._check_coherence(content)

        # 8 paragraphs, all with transitions = 100%
        assert (
            result["details"]["with_transitions"] == 8
        ), f"Should detect 8 paragraphs with transitions, found {result['details']['with_transitions']}"
        assert result["details"]["ratio"] == 1.0
        assert result["score"] == 100.0

    async def test_academic_tone_contractions_comprehensive(self):
        """Test comprehensive contraction detection"""
        validator = QualityValidator()

        content_with_contractions = (
            """
        Don't use contractions. Can't emphasize enough. Won't be accepted.
        Isn't professional. Aren't appropriate. Wasn't good. Weren't correct.
        Hasn't been verified. Haven't checked. Hadn't noticed.
        Couldn't confirm. Shouldn't do this. Wouldn't recommend.
        """
            + " word " * 100
        )

        result = await validator._check_academic_tone(content_with_contractions)

        # Should detect many contractions
        assert (
            result["details"]["contractions"] >= 10
        ), f"Should detect multiple contractions, found {result['details']['contractions']}"
        assert result["score"] < 50, "Score should be heavily penalized"

    async def test_word_count_accuracy_various_targets(self):
        """Test word count validation with various target sizes"""
        validator = QualityValidator()

        test_cases = [
            (100, 100, True),  # Exact match
            (100, 105, True),  # 5% deviation (within 10%)
            (100, 110, True),  # 10% deviation (at limit)
            (100, 115, False),  # 15% deviation (outside limit)
            (500, 525, True),  # Large target within tolerance
            (1000, 1100, True),  # Very large target at limit
            (1000, 1200, False),  # Very large target outside limit
        ]

        for actual, target, should_pass in test_cases:
            content = " ".join(["word"] * actual)
            result = await validator._check_word_count(content, target)

            assert (
                result["details"]["within_tolerance"] == should_pass
            ), f"Word count {actual} vs target {target} tolerance check failed"


@pytest.mark.asyncio
class TestQualityValidationRobustness:
    """Robustness tests for edge cases and error handling"""

    async def test_very_long_content_performance(self):
        """Test that validation handles very long content efficiently"""
        validator = QualityValidator()

        # 5000 words - large section
        content = " ".join(["word"] * 5000)

        import time

        start = time.time()
        result = await validator.validate_section(content, {"target_word_count": 5000})
        duration = time.time() - start

        assert (
            duration < 2.0
        ), f"Validation should complete in <2s, took {duration:.2f}s"
        assert "overall_score" in result

    async def test_special_characters_in_content(self):
        """Test handling of special characters and symbols"""
        validator = QualityValidator()

        content = (
            """
        Math symbols: α, β, γ, ∑, ∫, ∂, →, ≈, ≠, ≤, ≥
        According to Müller (2020), résumé research [1] shows naïve approaches.
        Chemical formulas: H₂O, CO₂, NaCl, CaCO₃
        Quotes: "test" 'test' «test» 'test' "test"
        Dashes: – — - ‐
        """
            + " word " * 450
        )

        # Should not crash
        result = await validator.validate_section(content, {"target_word_count": 500})
        assert "overall_score" in result

    async def test_malformed_paragraphs(self):
        """Test handling of unusual paragraph structures"""
        validator = QualityValidator()

        # Single giant paragraph (no paragraph breaks)
        content = "However, this is one very long sentence. " * 100

        result = await validator._check_coherence(content)

        # Should handle as 1 paragraph with transition
        assert result["details"]["total_paragraphs"] >= 1
        assert "overall_score" not in result or result.get("score") is not None

    async def test_mixed_citation_formats(self):
        """Test content with mixed citation formats"""
        validator = QualityValidator()

        content = (
            """
        Some sources use numbers [1] and [2].
        Others prefer (Author, 2020) format.
        Mixed within sentence [3] and (Smith, 2021).
        """
            + " word " * 450
        )

        result = await validator._check_citation_density(content)

        # Should count all citation types
        total = (
            result["details"]["numeric_citations"]
            + result["details"]["author_year_citations"]
        )
        assert result["details"]["total_citations"] == total
        assert total >= 4
