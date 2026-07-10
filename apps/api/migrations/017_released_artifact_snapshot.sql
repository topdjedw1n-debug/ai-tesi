-- Migration: Bind release to the exact stored artifact paths
-- Date: 2026-07-10
-- Description: A later regeneration must not inherit an earlier release.

ALTER TABLE production_cases
    ADD COLUMN IF NOT EXISTS released_docx_path VARCHAR(500),
    ADD COLUMN IF NOT EXISTS released_pdf_path VARCHAR(500);

COMMENT ON COLUMN production_cases.released_docx_path IS
    'DOCX object path that existed when the case was released.';
COMMENT ON COLUMN production_cases.released_pdf_path IS
    'PDF object path that existed when the case was released.';
