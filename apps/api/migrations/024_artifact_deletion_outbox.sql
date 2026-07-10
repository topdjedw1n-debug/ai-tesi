-- 024: durable retry queue for object-storage deletions.
--
-- Superseded/unbound artifact blobs were deleted best-effort after commit:
-- a MinIO failure was only logged and the file stayed in storage forever
-- (audit 2026-07-10). Deletion intents are now enqueued in the SAME
-- transaction that supersedes the artifact; the generation worker retries
-- them with exponential backoff until storage confirms.
--
-- GDPR account deletion and per-document deletion stay fail-closed and do
-- not rely on this queue.

CREATE TABLE IF NOT EXISTS artifact_deletion_outbox (
    id SERIAL PRIMARY KEY,
    file_path TEXT NOT NULL UNIQUE,
    reason VARCHAR(100) NOT NULL DEFAULT 'superseded',
    attempts INTEGER NOT NULL DEFAULT 0,
    next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    last_error TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_artifact_deletion_outbox_due
    ON artifact_deletion_outbox (next_attempt_at);
