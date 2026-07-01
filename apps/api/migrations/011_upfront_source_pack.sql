-- Migration: Upfront topic-locked source pack
-- Date: 2026-07-01
-- Description: Adds citation_key, on_topic_score, is_in_upfront_pack to
--              document_sources so the document-level, topic-locked source
--              pack (source_pack.py) can be persisted once and reused for the
--              outline + every section with stable, collision-safe keys.
--              citation_key is unique per document (partial index, mirroring
--              the existing uq_document_sources_document_id_doi style).
-- Rollback:
--   DROP INDEX IF EXISTS uq_document_sources_document_id_citation_key;
--   DROP INDEX IF EXISTS ix_document_sources_is_in_upfront_pack;
--   ALTER TABLE document_sources DROP COLUMN IF EXISTS citation_key;
--   ALTER TABLE document_sources DROP COLUMN IF EXISTS on_topic_score;
--   ALTER TABLE document_sources DROP COLUMN IF EXISTS is_in_upfront_pack;

ALTER TABLE document_sources
    ADD COLUMN IF NOT EXISTS citation_key       VARCHAR(64),
    ADD COLUMN IF NOT EXISTS on_topic_score     DOUBLE PRECISION,
    ADD COLUMN IF NOT EXISTS is_in_upfront_pack BOOLEAN NOT NULL DEFAULT FALSE;

-- Stable key must be unique per document; only pack rows carry a key.
CREATE UNIQUE INDEX IF NOT EXISTS uq_document_sources_document_id_citation_key
    ON document_sources (document_id, citation_key)
    WHERE citation_key IS NOT NULL;

CREATE INDEX IF NOT EXISTS ix_document_sources_is_in_upfront_pack
    ON document_sources (document_id, is_in_upfront_pack);

COMMENT ON COLUMN document_sources.citation_key IS
    'Stable pack-scoped citation key (e.g. Rossi2021, Rossi2021b) assigned by SourcePackBuilder; unique per document.';
COMMENT ON COLUMN document_sources.on_topic_score IS
    'Topic-relevance score [0,1] vs document.topic at pack-build time; below-threshold sources are excluded from the pack.';
COMMENT ON COLUMN document_sources.is_in_upfront_pack IS
    'True for rows that belong to the upfront document-level source pack reused across the outline + all sections.';
