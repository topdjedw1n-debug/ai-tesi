-- Migration: Add missing columns to database tables
-- Date: 2026-01-24
-- Description: Adds columns that were missing from initial schema

-- user_sessions table
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS is_active BOOLEAN DEFAULT TRUE;
ALTER TABLE user_sessions ADD COLUMN IF NOT EXISTS last_activity TIMESTAMP WITH TIME ZONE DEFAULT NOW();

-- ai_generation_jobs table
ALTER TABLE ai_generation_jobs ADD COLUMN IF NOT EXISTS ai_provider VARCHAR(50);
ALTER TABLE ai_generation_jobs ADD COLUMN IF NOT EXISTS ai_model VARCHAR(100);
ALTER TABLE ai_generation_jobs ADD COLUMN IF NOT EXISTS total_tokens INTEGER DEFAULT 0;
ALTER TABLE ai_generation_jobs ADD COLUMN IF NOT EXISTS cost_cents INTEGER DEFAULT 0;
ALTER TABLE ai_generation_jobs ADD COLUMN IF NOT EXISTS success BOOLEAN DEFAULT TRUE;

-- documents table
ALTER TABLE documents ADD COLUMN IF NOT EXISTS is_public BOOLEAN DEFAULT FALSE;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS temperature FLOAT DEFAULT 0.7;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS outline JSONB;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS docx_path VARCHAR(500);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS pdf_path VARCHAR(500);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS custom_requirements_file_path VARCHAR(500);
ALTER TABLE documents ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0;
ALTER TABLE documents ADD COLUMN IF NOT EXISTS generation_time_seconds INTEGER DEFAULT 0;

-- document_sections table
ALTER TABLE document_sections ADD COLUMN IF NOT EXISTS grammar_score FLOAT;
ALTER TABLE document_sections ADD COLUMN IF NOT EXISTS plagiarism_score FLOAT;
ALTER TABLE document_sections ADD COLUMN IF NOT EXISTS ai_detection_score FLOAT;
ALTER TABLE document_sections ADD COLUMN IF NOT EXISTS quality_score FLOAT;
ALTER TABLE document_sections ADD COLUMN IF NOT EXISTS tokens_used INTEGER DEFAULT 0;
ALTER TABLE document_sections ADD COLUMN IF NOT EXISTS generation_time_seconds INTEGER DEFAULT 0;
ALTER TABLE document_sections ADD COLUMN IF NOT EXISTS completed_at TIMESTAMP WITH TIME ZONE;
