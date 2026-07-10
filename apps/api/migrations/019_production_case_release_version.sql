-- Migration: Version each release so old signed URLs never become valid again
-- Date: 2026-07-10

ALTER TABLE production_cases
    ADD COLUMN IF NOT EXISTS release_version INTEGER NOT NULL DEFAULT 0;

COMMENT ON COLUMN production_cases.release_version IS
    'Monotonically increasing release version embedded in client download tokens.';
