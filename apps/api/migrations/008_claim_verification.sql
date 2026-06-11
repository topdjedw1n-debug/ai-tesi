-- Migration: Claim Faithfulness Audit (advisory)
-- Date: 2026-06-11
-- Description: Adds document_sections.claim_verification - per-claim verdicts
--              from the LLM claim-faithfulness pass (claim_verifier.py).
--              Advisory only: unsupported claims never block generation.
-- Rollback: ALTER TABLE document_sections DROP COLUMN IF EXISTS claim_verification;

ALTER TABLE document_sections
    ADD COLUMN IF NOT EXISTS claim_verification JSONB;

COMMENT ON COLUMN document_sections.claim_verification IS
    'Advisory claim-faithfulness audit: {"total", "checked", "counts": {supported|unsupported|uncertain}, "claims": [{sentence, citation, source_title, verdict, explanation, checked_by_llm}]}';
