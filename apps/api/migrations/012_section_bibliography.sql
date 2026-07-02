-- Migration: Per-section bibliography persistence
-- Date: 2026-07-02
-- Description: Adds document_sections.bibliography (formatted reference
--              strings from the final accepted generation attempt) and
--              document_sections.pack_keys_used (source-pack citation keys
--              actually cited) so the document-level "Bibliografia" section
--              can be assembled, previewed and exported after the background
--              job ends. Without persistence the bibliography built by
--              SectionGenerator is lost: checkpoint-resume skips completed
--              sections, so their in-memory results are gone at assembly.
-- Rollback:
--   ALTER TABLE document_sections DROP COLUMN IF EXISTS bibliography;
--   ALTER TABLE document_sections DROP COLUMN IF EXISTS pack_keys_used;

ALTER TABLE document_sections
    ADD COLUMN IF NOT EXISTS bibliography   JSONB,
    ADD COLUMN IF NOT EXISTS pack_keys_used JSONB;

COMMENT ON COLUMN document_sections.bibliography IS
    'List[str] of formatted references (APA/MLA/Chicago) cited by this section''s final accepted content attempt.';
COMMENT ON COLUMN document_sections.pack_keys_used IS
    'List[str] of upfront source-pack citation keys actually cited in this section (empty on legacy non-pack path).';
