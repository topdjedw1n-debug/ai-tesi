-- Migration: Add quality score fields to document_sections table
-- Created: 2025-11-30
-- Description: Add grammar_score and plagiarism_score columns for quality tracking

-- Add grammar_score column (0-100, higher is better)
ALTER TABLE document_sections
ADD COLUMN IF NOT EXISTS grammar_score FLOAT NULL;

-- Add plagiarism_score column (0-100, lower is better - percentage of plagiarism)
ALTER TABLE document_sections
ADD COLUMN IF NOT EXISTS plagiarism_score FLOAT NULL;

-- Add comments for documentation
COMMENT ON COLUMN document_sections.grammar_score IS 'Grammar quality score (0-100, higher is better). NULL if not checked.';
COMMENT ON COLUMN document_sections.plagiarism_score IS 'Plagiarism percentage (0-100, lower is better). NULL if not checked.';
