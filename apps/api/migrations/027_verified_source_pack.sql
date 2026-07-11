-- 027: verified/frozen source pack before section writing.
--
-- Automatic retrieval now preserves provider/type metadata so student
-- dissertations can be excluded before writing.  The generation job stores a
-- digest of the exact verified pack; crash recovery must reuse that same pack.

ALTER TABLE document_sources
    ADD COLUMN IF NOT EXISTS retrieval_provider VARCHAR(50);
ALTER TABLE document_sources
    ADD COLUMN IF NOT EXISTS source_type VARCHAR(100);
ALTER TABLE ai_generation_jobs
    ADD COLUMN IF NOT EXISTS source_pack_sha256 CHAR(64);
ALTER TABLE ai_generation_jobs
    ADD COLUMN IF NOT EXISTS claim_checks_used INTEGER NOT NULL DEFAULT 0;
