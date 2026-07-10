-- Migration: Track successful university methodology processing
-- Date: 2026-07-10
-- Description: Provides a durable generation gate. Extracted text alone is
--              not enough to distinguish a real processed upload from text a
--              caller typed into the requirements field.
-- Rollback:
--   ALTER TABLE documents DROP COLUMN IF EXISTS requirements_file_processed;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS requirements_file_processed BOOLEAN NOT NULL DEFAULT FALSE;

COMMENT ON COLUMN documents.requirements_file_processed IS
    'True only after a requirements PDF, DOCX, or TXT file was validated, parsed, and persisted.';
