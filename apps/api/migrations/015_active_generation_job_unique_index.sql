-- Migration: Enforce one active generation job per document and job type
-- Date: 2026-07-10
-- Description: Prevents two workers from owning the same queued/running job
--              after future automatic recovery or concurrent API requests.
--
-- If this migration fails because active duplicates already exist, reconcile
-- those jobs explicitly before retrying. The migration deliberately does not
-- guess which in-flight job should be kept.
--
-- Rollback:
--   DROP INDEX IF EXISTS uq_ai_generation_jobs_active_document_job_type;

CREATE UNIQUE INDEX IF NOT EXISTS uq_ai_generation_jobs_active_document_job_type
    ON ai_generation_jobs (document_id, job_type)
    WHERE status IN ('queued', 'running');
