"""One non-secret compatibility contract for enqueue, review, resume and claim."""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Any

from app.core.config import settings
from app.services.academic_context import ACADEMIC_POLICY_VERSION, digest

PIPELINE_VERSION = "stability-v1"
PROFILE_SETTINGS = (
    "METHODOLOGY_REQUIRED_FOR_GENERATION",
    "AI_RETRY_DELAYS",
    "PROVENANCE_LEDGER_ENABLED",
    "AI_ENABLE_FALLBACK",
    "AI_MAX_RETRIES",
    "PARTIAL_COMPLETION_ENABLED",
    "HUMANIZER_PROVIDER",
    "HUMANIZER_MODEL",
    "HUMANIZER_BEST_OF_N",
    "HUMANIZER_FREEZE_CITATIONS",
    "QUALITY_MAX_GRAMMAR_ERRORS",
    "QUALITY_MAX_GRAMMAR_ERRORS_NON_EN",
    "AI_DETECTION_ENABLED",
    "AI_FALLBACK_CHAIN",
    "SOURCE_GROUNDING_ENABLED",
    "SOURCE_PACK_PREFLIGHT_ENABLED",
    "SOURCE_PACK_TARGET_SIZE",
    "SOURCE_PACK_CANDIDATE_RESERVE_SIZE",
    "SOURCE_PACK_MIN_VERIFIED",
    "SOURCE_PACK_MIN_ON_TOPIC_SCORE",
    "GROUNDING_GATE_ENABLED",
    "GROUNDING_GATE_POLICY",
    "CITATION_VERIFICATION_ENABLED",
    "CITATION_VERIFICATION_POLICY",
    "CLAIM_VERIFICATION_ENABLED",
    "CLAIM_VERIFICATION_BLOCKING",
    "CLAIM_VERIFICATION_MAX_CHECKS",
    "QUALITY_GATES_ENABLED",
    "QUALITY_PANEL_ENABLED",
    "HUMANIZER_ENABLED",
    "AI_DETECTION_BLOCKING",
    "QUALITY_JUDGE_PROVIDER",
    "QUALITY_JUDGE_MODEL",
    "QUALITY_PANEL_PASS_SCORE",
    "QUALITY_PANEL_MIN_REVIEWERS",
    "CLAIM_ABSTRACT_MAX_CHARS",
    "CLAIM_VERIFICATION_BATCH_SIZE",
    "QUALITY_MAX_REGENERATE_ATTEMPTS",
    "QUALITY_MIN_PLAGIARISM_UNIQUENESS",
    "QUALITY_MAX_AI_DETECTION_SCORE",
    "SOURCE_PACK_BILINGUAL_ENABLED",
)
PROMPT_FILES = (
    "academic_context.py",
    "academic_review.py",
    "plan_preparation.py",
    "generation_policy.py",
    "standard_references.py",
    "ai_service.py",
    "ai_pipeline/prompt_builder.py",
    "ai_pipeline/humanizer.py",
    "claim_verifier.py",
)


def generation_profile(document: Any, user_id: int | None = None) -> dict[str, Any]:
    root = Path(__file__).parent
    return {
        "pipeline": PIPELINE_VERSION,
        "academic_policy": ACADEMIC_POLICY_VERSION,
        "prompts": {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in PROMPT_FILES
        },
        "writer": [str(document.ai_provider), str(document.ai_model)],
        "settings": {name: getattr(settings, name) for name in PROFILE_SETTINGS},
        "unlimited_claim_checks": (user_id if user_id is not None else document.user_id)
        in settings.UNLIMITED_GENERATION_USER_IDS,
    }


def generation_profile_sha256(document: Any, user_id: int | None = None) -> str:
    return digest(generation_profile(document, user_id))
