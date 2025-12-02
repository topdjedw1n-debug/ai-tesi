-- Migration: Add password_hash to users table
-- Created: 2025-11-29
-- Description: Add password_hash column for admin authentication (bcrypt hashed passwords)
-- Related to: Admin Auth fix - AttributeError bug

-- Add password_hash column to users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS password_hash VARCHAR(255);

-- Add comment
COMMENT ON COLUMN users.password_hash IS 'Bcrypt hashed password for admin login. NULL for regular users using magic links.';
