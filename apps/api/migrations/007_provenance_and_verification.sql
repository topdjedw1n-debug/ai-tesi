-- Migration: Provenance and Source Verification Foundation
-- Date: 2026-06-11
-- Description: Adds document_provenance (pipeline audit trail) and document_sources
--              (persisted RAG sources with verification state) for the Academic
--              Quality Engine. Foundation only - no pipeline behavior changes.
-- Rollback: DROP TABLE IF EXISTS document_sources; DROP TABLE IF EXISTS document_provenance;

-- 1. Provenance events: append-only audit trail of pipeline stages
CREATE TABLE IF NOT EXISTS document_provenance (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    stage VARCHAR(50) NOT NULL,
    event_type VARCHAR(100) NOT NULL,
    payload JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_document_provenance_document_id
    ON document_provenance(document_id);
CREATE INDEX IF NOT EXISTS ix_document_provenance_document_id_stage
    ON document_provenance(document_id, stage);
CREATE INDEX IF NOT EXISTS ix_document_provenance_created_at
    ON document_provenance(created_at);

COMMENT ON COLUMN document_provenance.stage IS 'Pipeline stage: retrieval, outline, generation, quality, verification, export';
COMMENT ON COLUMN document_provenance.event_type IS 'Event within stage, e.g. sources_retrieved, source_verified, citation_flagged';
COMMENT ON COLUMN document_provenance.payload IS 'Arbitrary structured event data';

-- 2. Persisted sources retrieved for a document (raw fields mirror the SourceDoc
--    dataclass in app/services/ai_pipeline/rag_retriever.py)
CREATE TABLE IF NOT EXISTS document_sources (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    section_id INTEGER REFERENCES document_sections(id) ON DELETE SET NULL,

    -- Raw retrieval metadata (SourceDoc keys)
    title VARCHAR(1000) NOT NULL,
    authors JSONB,
    year INTEGER,
    abstract TEXT,
    paper_id VARCHAR(100),
    venue VARCHAR(500),
    citation_count INTEGER,
    url VARCHAR(1000),
    doi VARCHAR(255),

    -- Verification state
    verification_status VARCHAR(50) NOT NULL DEFAULT 'unverified',
    canonical_metadata JSONB,

    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_document_sources_document_id
    ON document_sources(document_id);
CREATE INDEX IF NOT EXISTS ix_document_sources_section_id
    ON document_sources(section_id);
CREATE INDEX IF NOT EXISTS ix_document_sources_verification_status
    ON document_sources(verification_status);

-- Dedup guard: one row per (document, DOI). Partial so DOI-less sources are unconstrained.
CREATE UNIQUE INDEX IF NOT EXISTS uq_document_sources_document_id_doi
    ON document_sources(document_id, doi) WHERE doi IS NOT NULL;

COMMENT ON COLUMN document_sources.authors IS 'JSON array of author names (list[str] from SourceDoc)';
COMMENT ON COLUMN document_sources.doi IS 'Normalized (lowercased) DOI; uniqueness is per document';
COMMENT ON COLUMN document_sources.verification_status IS 'unverified, verified, mismatched, not_found, failed';
COMMENT ON COLUMN document_sources.canonical_metadata IS 'Normalized record from Crossref/OpenAlex/Semantic Scholar/arXiv after verification';
