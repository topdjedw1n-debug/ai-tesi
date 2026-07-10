-- Migration: serialize GDPR deletion against durable generation enqueue
-- Date: 2026-07-10
-- Description: Persist account-deletion intent and prevent any new or
--              reactivated generation job from creating personal data after it.

ALTER TABLE users
    ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMPTZ;

COMMENT ON COLUMN users.deletion_requested_at IS
    'Durable GDPR deletion intent; generation remains blocked even when cleanup must be retried.';

CREATE OR REPLACE FUNCTION block_generation_for_deleting_user()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
DECLARE
    deletion_started_at TIMESTAMPTZ;
BEGIN
    IF NEW.status NOT IN ('queued', 'running') THEN
        RETURN NEW;
    END IF;

    -- Worker lease transitions remain safe because queued/running jobs are
    -- already visible to GDPR deletion. Only a newly active historical row
    -- needs to acquire the user fence.
    IF TG_OP = 'UPDATE' THEN
        IF OLD.status IN ('queued', 'running') THEN
            RETURN NEW;
        END IF;
    END IF;

    SELECT deletion_requested_at
      INTO deletion_started_at
      FROM users
     WHERE id = NEW.user_id
       FOR KEY SHARE;

    IF deletion_started_at IS NOT NULL THEN
        RAISE EXCEPTION 'generation blocked: account deletion requested'
            USING ERRCODE = '23514',
                  CONSTRAINT = 'ck_generation_user_not_deleting';
    END IF;

    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_generation_job_block_deleting_user_insert
    ON ai_generation_jobs;
CREATE TRIGGER trg_generation_job_block_deleting_user_insert
BEFORE INSERT ON ai_generation_jobs
FOR EACH ROW
EXECUTE FUNCTION block_generation_for_deleting_user();

DROP TRIGGER IF EXISTS trg_generation_job_block_deleting_user_update
    ON ai_generation_jobs;
CREATE TRIGGER trg_generation_job_block_deleting_user_update
BEFORE UPDATE OF user_id, status ON ai_generation_jobs
FOR EACH ROW
WHEN (
    NEW.status IN ('queued', 'running')
    AND OLD.status NOT IN ('queued', 'running')
)
EXECUTE FUNCTION block_generation_for_deleting_user();
