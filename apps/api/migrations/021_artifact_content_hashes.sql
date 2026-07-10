-- Migration: Bind generation, detector evidence, release, and download to bytes
-- Date: 2026-07-10

ALTER TABLE documents
    ADD COLUMN IF NOT EXISTS docx_sha256 VARCHAR(64),
    ADD COLUMN IF NOT EXISTS pdf_sha256 VARCHAR(64);

ALTER TABLE production_cases
    ADD COLUMN IF NOT EXISTS released_docx_sha256 VARCHAR(64),
    ADD COLUMN IF NOT EXISTS released_pdf_sha256 VARCHAR(64);

COMMENT ON COLUMN documents.docx_sha256 IS
    'SHA-256 of the exact generated DOCX bytes stored at docx_path.';
COMMENT ON COLUMN documents.pdf_sha256 IS
    'SHA-256 of the exact generated PDF bytes stored at pdf_path.';
COMMENT ON COLUMN production_cases.released_docx_sha256 IS
    'SHA-256 snapshot of the DOCX bytes approved at release.';
COMMENT ON COLUMN production_cases.released_pdf_sha256 IS
    'SHA-256 snapshot of the PDF bytes approved at release.';
