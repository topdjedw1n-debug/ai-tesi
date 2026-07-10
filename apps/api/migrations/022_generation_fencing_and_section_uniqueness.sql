-- Migration: Per-acquisition generation fencing and unique document sections
-- Date: 2026-07-10
--
-- A worker identity is not a fencing token: the same process can reacquire a
-- stale job while its old coroutine is still alive.  A fresh lease_token is
-- therefore minted on every claim and must accompany every generation write.
--
-- Active jobs created before this contract cannot prove that they contain the
-- complete methodology/APA payload.  Fail them closed instead of letting a new
-- worker resume unsafe legacy input after deployment.

ALTER TABLE ai_generation_jobs
    ADD COLUMN IF NOT EXISTS lease_token VARCHAR(64);

UPDATE documents
SET status = 'failed'
WHERE id IN (
    SELECT document_id
    FROM ai_generation_jobs
    WHERE job_type = 'full_document'
      AND status IN ('queued', 'running')
      AND document_id IS NOT NULL
)
  AND status <> 'failed_quality';

UPDATE production_cases
SET generation_status = 'failed',
    delivery_status = 'not_ready',
    release_status = 'blocked',
    released_at = NULL,
    released_docx_path = NULL,
    released_pdf_path = NULL,
    released_docx_sha256 = NULL,
    released_pdf_sha256 = NULL,
    release_version = COALESCE(release_version, 0) + 1
WHERE document_id IN (
    SELECT document_id
    FROM ai_generation_jobs
    WHERE job_type = 'full_document'
      AND status IN ('queued', 'running')
      AND document_id IS NOT NULL
);

UPDATE ai_generation_jobs
SET status = 'failed',
    success = FALSE,
    error_message = 'Quarantined during fencing migration: restart generation with current methodology and APA contract',
    completed_at = NOW(),
    heartbeat_at = NOW(),
    lease_owner = NULL,
    lease_token = NULL,
    lease_expires_at = NULL
WHERE job_type = 'full_document'
  AND status IN ('queued', 'running');

-- Historical databases may contain duplicate rows from the old read-then-
-- insert section path.  Keep the strongest/latest row so the unique index can
-- be installed without turning deployment into a partial migration.
WITH ranked_sections AS (
    SELECT
        id,
        ROW_NUMBER() OVER (
            PARTITION BY document_id, section_index
            ORDER BY
                CASE status
                    WHEN 'completed' THEN 0
                    WHEN 'generating' THEN 1
                    WHEN 'pending' THEN 2
                    ELSE 3
                END,
                id DESC
        ) AS duplicate_rank
    FROM document_sections
)
DELETE FROM document_sections
WHERE id IN (
    SELECT id
    FROM ranked_sections
    WHERE duplicate_rank > 1
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_document_sections_document_section_index
    ON document_sections (document_id, section_index);

COMMENT ON COLUMN ai_generation_jobs.lease_token IS
    'Fresh unguessable fencing token minted for each lease acquisition.';
