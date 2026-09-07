"""ISSUE-007: diagnostic providers cannot duplicate final Compilatio gates.

Found by /qa on 2026-09-07 after the real isolated pipeline reached DOCX.
Report: .gstack/qa-reports/qa-report-localhost-2026-09-07.md
"""

import copy

import pytest

from app.services.release_policy import section_release_status


@pytest.mark.parametrize("detector_status", ["unchecked", "failed", "passed"])
@pytest.mark.parametrize(
    "grammar,expected",
    [("passed", "passed"), ("failed", "failed"), ("unchecked", "unchecked")],
)
def test_diagnostics_do_not_mask_or_duplicate_section_checks(
    detector_status, grammar, expected
):
    payload = {
        "status": detector_status,
        "checks": {
            "grammar": {"status": grammar},
            "plagiarism": {"status": detector_status},
            "ai_detection": {"status": detector_status, "blocking": False},
        },
    }
    original = copy.deepcopy(payload)
    assert section_release_status(payload) == expected
    assert payload == original


@pytest.mark.parametrize(
    "payload",
    [
        {"checks": {"plagiarism": {"status": "passed"}}},
        {"checks": {"grammar": None}},
        {"checks": {"grammar": {"status": "passed"}}, "gates_enabled": False},
        {"passed": True, "grammar_score": None},
    ],
)
def test_missing_or_disabled_grammar_never_passes(payload):
    assert section_release_status(payload) == "unchecked"


def test_unexplained_aggregate_failure_remains_blocking():
    assert (
        section_release_status(
            {
                "status": "failed",
                "checks": {
                    "grammar": {"status": "passed"},
                    "plagiarism": {"status": "unchecked"},
                    "ai_detection": {"status": "unchecked", "blocking": False},
                },
            }
        )
        == "failed"
    )
