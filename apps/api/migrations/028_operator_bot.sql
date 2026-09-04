-- Additive; safe to leave in place when rolling back the bot/API image.
BEGIN;
CREATE TABLE IF NOT EXISTS operator_bot_actions (
    id VARCHAR(32) PRIMARY KEY,
    telegram_user_id VARCHAR(32) NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id INTEGER NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    fingerprint VARCHAR(64) NOT NULL,
    last_job_id INTEGER,
    retry_reason TEXT,
    result JSON,
    expires_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
CREATE TABLE IF NOT EXISTS operator_support_requests (
    id VARCHAR(32) PRIMARY KEY,
    telegram_user_id VARCHAR(32) NOT NULL,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    document_id INTEGER REFERENCES documents(id) ON DELETE SET NULL,
    summary TEXT NOT NULL,
    evidence JSON NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending_review',
    created_at TIMESTAMPTZ DEFAULT now()
);
COMMIT;
