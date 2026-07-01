"""Validator tests for the source-grounding config flags (WS7)."""

import pytest

from app.core.config import Settings


def test_defaults_are_off():
    s = Settings()
    assert s.SOURCE_GROUNDING_ENABLED is False
    assert s.GROUNDING_GATE_ENABLED is False
    assert s.GROUNDING_GATE_POLICY == "mark_only"
    assert s.CLAIM_VERIFICATION_BLOCKING is False
    assert s.SOURCE_PACK_TARGET_SIZE == 24


def test_grounding_gate_requires_source_grounding():
    with pytest.raises(ValueError):
        Settings(GROUNDING_GATE_ENABLED=True, SOURCE_GROUNDING_ENABLED=False)


def test_grounding_gate_valid_combo():
    s = Settings(GROUNDING_GATE_ENABLED=True, SOURCE_GROUNDING_ENABLED=True)
    assert s.GROUNDING_GATE_ENABLED is True


def test_bad_grounding_policy_rejected():
    with pytest.raises(ValueError):
        Settings(GROUNDING_GATE_POLICY="loose")


def test_grounding_policy_normalized():
    assert Settings(GROUNDING_GATE_POLICY="STRICT").GROUNDING_GATE_POLICY == "strict"


def test_claim_blocking_requires_claim_enabled():
    with pytest.raises(ValueError):
        Settings(CLAIM_VERIFICATION_BLOCKING=True, CLAIM_VERIFICATION_ENABLED=False)


def test_claim_blocking_valid_combo():
    s = Settings(
        CITATION_VERIFICATION_ENABLED=True,
        CLAIM_VERIFICATION_ENABLED=True,
        CLAIM_VERIFICATION_BLOCKING=True,
    )
    assert s.CLAIM_VERIFICATION_BLOCKING is True
