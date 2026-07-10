-- Migration: Make document deletion compatible with dependent production data
-- Date: 2026-07-10
-- Description: Document-owned generation data is deleted with the document;
--              financial payment records are retained with document_id NULL.

ALTER TABLE document_sections
    DROP CONSTRAINT IF EXISTS document_sections_document_id_fkey,
    ADD CONSTRAINT document_sections_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;

ALTER TABLE document_outlines
    DROP CONSTRAINT IF EXISTS document_outlines_document_id_fkey,
    ADD CONSTRAINT document_outlines_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;

ALTER TABLE ai_generation_jobs
    DROP CONSTRAINT IF EXISTS ai_generation_jobs_document_id_fkey,
    ADD CONSTRAINT ai_generation_jobs_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;

ALTER TABLE document_drafts
    DROP CONSTRAINT IF EXISTS document_drafts_document_id_fkey,
    ADD CONSTRAINT document_drafts_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE CASCADE;

ALTER TABLE payments
    DROP CONSTRAINT IF EXISTS payments_document_id_fkey,
    ADD CONSTRAINT payments_document_id_fkey
        FOREIGN KEY (document_id) REFERENCES documents(id) ON DELETE SET NULL;
