"""Validator tests for the source-grounding config flags (WS7 + fix-wave 2).

All constructions use _env_file=None so a developer's local .env (which may
legitimately enable grounding, as ours does) can't flip the code defaults
under test — the same leak that bit test_config_guards.
"""

import os

import pytest

# Required env vars so Settings(_env_file=None) constructs in a bare test env.
os.environ.setdefault("SECRET_KEY", "test-secret-key-minimum-32-chars-long-1234567890")
os.environ.setdefault(
    "JWT_SECRET", "test-jwt-secret-UWX2ud0E0fcvV8xNIqhn7wUuLUPEsliTstJMFwg4AsI"
)
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("ENVIRONMENT", "test")

from app.core.config import Settings


def make(**overrides) -> Settings:
    """Settings isolated from .env — code defaults + explicit overrides only."""
    return Settings(_env_file=None, **overrides)


def test_defaults_are_off():
    s = make()
    assert s.SOURCE_GROUNDING_ENABLED is False
    assert s.GROUNDING_GATE_ENABLED is False
    assert s.GROUNDING_GATE_POLICY == "mark_only"
    assert s.CLAIM_VERIFICATION_BLOCKING is False
    assert s.SOURCE_PACK_TARGET_SIZE == 24
    assert s.SOURCE_PACK_PREFLIGHT_ENABLED is False
    assert s.SOURCE_PACK_CANDIDATE_RESERVE_SIZE == 48
    assert s.SOURCE_PACK_MIN_VERIFIED == 18
    # Bilingual pack is ON by default (kill switch for bad translations);
    # it only activates when grounding itself is enabled.
    assert s.SOURCE_PACK_BILINGUAL_ENABLED is True


def test_grounding_gate_requires_source_grounding():
    with pytest.raises(ValueError):
        make(GROUNDING_GATE_ENABLED=True, SOURCE_GROUNDING_ENABLED=False)


def test_grounding_gate_valid_combo():
    s = make(GROUNDING_GATE_ENABLED=True, SOURCE_GROUNDING_ENABLED=True)
    assert s.GROUNDING_GATE_ENABLED is True


def test_bad_grounding_policy_rejected():
    with pytest.raises(ValueError):
        make(GROUNDING_GATE_POLICY="loose")


def test_grounding_policy_normalized():
    assert make(GROUNDING_GATE_POLICY="STRICT").GROUNDING_GATE_POLICY == "strict"


def test_claim_blocking_requires_claim_enabled():
    with pytest.raises(ValueError):
        make(CLAIM_VERIFICATION_BLOCKING=True, CLAIM_VERIFICATION_ENABLED=False)


def test_claim_blocking_valid_combo():
    s = make(
        CITATION_VERIFICATION_ENABLED=True,
        CLAIM_VERIFICATION_ENABLED=True,
        CLAIM_VERIFICATION_BLOCKING=True,
    )
    assert s.CLAIM_VERIFICATION_BLOCKING is True


def test_grounding_require_evidence_default_and_override():
    assert make().GROUNDING_REQUIRE_EVIDENCE is True
    assert make(GROUNDING_REQUIRE_EVIDENCE=False).GROUNDING_REQUIRE_EVIDENCE is False


def test_source_pack_preflight_requires_full_strict_quality_profile():
    with pytest.raises(ValueError):
        make(SOURCE_PACK_PREFLIGHT_ENABLED=True)

    enabled = make(
        SOURCE_PACK_PREFLIGHT_ENABLED=True,
        SOURCE_GROUNDING_ENABLED=True,
        CITATION_VERIFICATION_ENABLED=True,
        CITATION_VERIFICATION_POLICY="strict",
        CLAIM_VERIFICATION_ENABLED=True,
        CLAIM_VERIFICATION_BLOCKING=True,
    )
    assert enabled.SOURCE_PACK_PREFLIGHT_ENABLED is True


@pytest.mark.parametrize(
    "override",
    [
        {"CITATION_VERIFICATION_POLICY": "mark_only"},
        {"CLAIM_VERIFICATION_ENABLED": False},
        {"CLAIM_VERIFICATION_BLOCKING": False},
        {"HUMANIZER_FREEZE_CITATIONS": False},
    ],
)
def test_source_pack_preflight_cannot_silently_run_advisory(override):
    values = {
        "SOURCE_PACK_PREFLIGHT_ENABLED": True,
        "SOURCE_GROUNDING_ENABLED": True,
        "CITATION_VERIFICATION_ENABLED": True,
        "CITATION_VERIFICATION_POLICY": "strict",
        "CLAIM_VERIFICATION_ENABLED": True,
        "CLAIM_VERIFICATION_BLOCKING": True,
    }
    values.update(override)
    with pytest.raises(ValueError):
        make(**values)


@pytest.mark.parametrize(
    "overrides",
    [
        {"SOURCE_PACK_MIN_VERIFIED": 0},
        {"SOURCE_PACK_MIN_VERIFIED": 25},
        {"SOURCE_PACK_CANDIDATE_RESERVE_SIZE": 23},
    ],
)
def test_source_pack_size_invariants(overrides):
    with pytest.raises(ValueError, match="minimum verified"):
        make(**overrides)
