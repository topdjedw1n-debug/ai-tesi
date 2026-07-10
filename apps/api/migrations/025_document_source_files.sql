-- 025: user-uploaded scientific PDFs as first-class, page-anchored sources.
--
-- Stage "full-text evidence" (2026-07-11): professor-mandated readings are
-- uploaded per document, parsed page by page, and become the grounding
-- source pack. Page-level text is what makes
-- "claim -> exact excerpt -> PDF -> page" evidence possible.

CREATE TABLE IF NOT EXISTS document_source_files (
    id SERIAL PRIMARY KEY,
    document_id INTEGER NOT NULL
        REFERENCES documents(id) ON DELETE CASCADE,
    filename VARCHAR(255) NOT NULL,
    citation_key VARCHAR(100) NOT NULL,
    title TEXT,
    authors TEXT,
    year INTEGER,
    storage_path TEXT NOT NULL,
    sha256 CHAR(64) NOT NULL,
    page_count INTEGER NOT NULL DEFAULT 0,
    text_chars INTEGER NOT NULL DEFAULT 0,
    status VARCHAR(30) NOT NULL DEFAULT 'parsed',  -- parsed | no_text_layer
    metadata_incomplete BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    -- The same PDF twice for one document is a manager mistake, not a feature.
    CONSTRAINT uq_document_source_files_doc_sha UNIQUE (document_id, sha256),
    -- Citation keys must be unambiguous within a document.
    CONSTRAINT uq_document_source_files_doc_key UNIQUE (document_id, citation_key)
);

CREATE INDEX IF NOT EXISTS ix_document_source_files_document
    ON document_source_files (document_id);

CREATE TABLE IF NOT EXISTS source_file_pages (
    id SERIAL PRIMARY KEY,
    source_file_id INTEGER NOT NULL
        REFERENCES document_source_files(id) ON DELETE CASCADE,
    page_number INTEGER NOT NULL,          -- 1-based, as printed in the PDF reader
    text TEXT NOT NULL,
    CONSTRAINT uq_source_file_pages_file_page UNIQUE (source_file_id, page_number)
);

CREATE INDEX IF NOT EXISTS ix_source_file_pages_file
    ON source_file_pages (source_file_id);
