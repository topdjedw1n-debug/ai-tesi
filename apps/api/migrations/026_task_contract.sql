-- 026: universal task contract (course decision 2026-07-11, ratified by owner).
--
-- The centre of the product is the requirements contract, not the
-- methodology file. Mandatory core = topic, work type, language, volume;
-- everything else (methodology, uploaded PDFs, wishes) enriches it. Every
-- derived rule carries a value, a source, and an explicit/assumed/confirmed
-- flag; works without a methodology run on a neutral academic structure
-- AFTER the manager confirms the assumptions.

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS work_type VARCHAR(50);

-- Confirmation binds to the exact contract fingerprint: any input change
-- shifts the sha and the stale confirmation stops blocking nothing.
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS contract_confirmed_sha256 CHAR(64);
ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS contract_confirmed_at TIMESTAMPTZ;

-- Uploaded scientific PDFs are SUPPLEMENTARY by default; a file becomes
-- mandatory only when the manager explicitly marks it so.
ALTER TABLE document_source_files
    ADD COLUMN IF NOT EXISTS mandatory BOOLEAN NOT NULL DEFAULT FALSE;
