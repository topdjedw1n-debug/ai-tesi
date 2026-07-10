-- Migration: Persist document citation style
-- Date: 2026-07-10
-- Description: Makes the manager-selected citation style durable so async
--              generation and bibliography formatting cannot fall back to APA.
-- Rollback:
--   ALTER TABLE documents DROP COLUMN IF EXISTS citation_style;

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS citation_style VARCHAR(50) NOT NULL DEFAULT 'apa';

COMMENT ON COLUMN documents.citation_style IS
    'Normalized citation style: apa, mla, chicago, or harvard.';
