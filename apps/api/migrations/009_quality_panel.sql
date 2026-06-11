-- Migration: Quality Reviewer Panel
-- Date: 2026-06-12
-- Description: Adds document_sections.quality_panel - detailed report of the
--              LLM reviewer panel (3 independent reviewers + devil's advocate,
--              quality_validator.py). The aggregate score keeps living in
--              document_sections.quality_score for backward compatibility.
-- Rollback: ALTER TABLE document_sections DROP COLUMN IF EXISTS quality_panel;

ALTER TABLE document_sections
    ADD COLUMN IF NOT EXISTS quality_panel JSONB;

COMMENT ON COLUMN document_sections.quality_panel IS
    'Reviewer panel report: {"valid", "overall_score", "passed", "critical_override", "reviewers": [{key, title, weight, ok, score, remarks: [{severity, text}]}], "advocate": {ok, severity, weakness}}';
