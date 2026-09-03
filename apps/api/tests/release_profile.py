"""Single expected runtime contract shared by release-profile tests."""

from typing import Any

RELEASE_PROFILE: dict[str, Any] = {
    "MVP_FREE_GENERATION_ENABLED": True,
    "MVP_FREE_GENERATION_MAX_PAGES": 50,
    "MVP_FREE_GENERATION_DAILY_USER_LIMIT": 2,
    "GLOBAL_DAILY_TOKEN_LIMIT": 6_000_000,
    "PUBLIC_REGISTRATION_ENABLED": False,
    "METHODOLOGY_REQUIRED_FOR_GENERATION": False,
    "LEGACY_GENERATION_ENDPOINTS_ENABLED": False,
    "AI_ENABLE_FALLBACK": False,
    "GENERATION_WORKER_ENABLED": True,
    "QUALITY_GATES_ENABLED": True,
    "PARTIAL_COMPLETION_ENABLED": False,
    "PROVENANCE_LEDGER_ENABLED": True,
    "SOURCE_GROUNDING_ENABLED": True,
    "SOURCE_PACK_PREFLIGHT_ENABLED": True,
    "SOURCE_PACK_TARGET_SIZE": 24,
    "SOURCE_PACK_CANDIDATE_RESERVE_SIZE": 48,
    "SOURCE_PACK_MIN_VERIFIED": 18,
    "SOURCE_PACK_MIN_ON_TOPIC_SCORE": 0.35,
    "GROUNDING_GATE_ENABLED": True,
    "GROUNDING_GATE_POLICY": "strict",
    "CITATION_VERIFICATION_ENABLED": True,
    "CITATION_VERIFICATION_POLICY": "strict",
    "CLAIM_VERIFICATION_ENABLED": True,
    "CLAIM_VERIFICATION_BLOCKING": True,
    "HUMANIZER_FREEZE_CITATIONS": True,
    "HUMANIZER_ENABLED": False,
    "QUALITY_PANEL_ENABLED": True,
    "AI_DETECTION_ENABLED": True,
    "AI_DETECTION_BLOCKING": False,
}


def release_profile_env() -> dict[str, str]:
    """Render the Python contract as docker-compose environment literals."""
    rendered: dict[str, str] = {}
    for key, value in RELEASE_PROFILE.items():
        if isinstance(value, bool):
            rendered[key] = str(value).lower()
        else:
            rendered[key] = str(value)
    return rendered
