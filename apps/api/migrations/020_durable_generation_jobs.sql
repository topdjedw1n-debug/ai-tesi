-- Migration: Durable database-backed full-document generation queue
-- Date: 2026-07-10
-- Description: Persist the generation payload, lease ownership, heartbeat,
--              scheduling, and bounded retry state needed for crash recovery.
--
-- Existing queued jobs become immediately available. Existing running jobs
-- have no lease owner and are therefore recoverable by the new worker after
-- deployment; the old in-process worker is stopped before this migration runs.

ALTER TABLE ai_generation_jobs
    ADD COLUMN IF NOT EXISTS request_payload JSONB,
    ADD COLUMN IF NOT EXISTS lease_owner VARCHAR(255),
    ADD COLUMN IF NOT EXISTS lease_expires_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS heartbeat_at TIMESTAMPTZ,
    ADD COLUMN IF NOT EXISTS available_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    ADD COLUMN IF NOT EXISTS attempt_count INTEGER NOT NULL DEFAULT 0,
    ADD COLUMN IF NOT EXISTS max_attempts INTEGER NOT NULL DEFAULT 3;

CREATE INDEX IF NOT EXISTS ix_ai_generation_jobs_worker_queue
    ON ai_generation_jobs (status, available_at, lease_expires_at, started_at)
    WHERE job_type = 'full_document'
      AND status IN ('queued', 'running');

COMMENT ON COLUMN ai_generation_jobs.request_payload IS
    'Durable per-run input consumed by the generation worker.';
COMMENT ON COLUMN ai_generation_jobs.lease_owner IS
    'Unique worker instance currently allowed to execute this job.';
COMMENT ON COLUMN ai_generation_jobs.lease_expires_at IS
    'Expired leases may be reclaimed by another worker after a crash.';
COMMENT ON COLUMN ai_generation_jobs.attempt_count IS
    'Number of execution leases acquired, including recovered attempts.';
