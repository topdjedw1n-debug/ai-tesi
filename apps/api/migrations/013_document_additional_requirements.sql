-- Migration: Persist document generation requirements
-- Date: 2026-07-10
-- Description: Keeps the sanitized creation-time requirements on the document
--              so asynchronous generation can recover them when a start request
--              contains only document_id.
-- Rollback:
--   ALTER TABLE documents DROP COLUMN IF EXISTS additional_requirements;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS additional_requirements TEXT;

COMMENT ON COLUMN documents.additional_requirements IS
    'Sanitized creation-time requirements used by full-document generation.';
