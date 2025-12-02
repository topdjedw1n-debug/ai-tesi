-- Migration: Add quality_score to document_sections
-- Description: Stores overall quality validation score (0-100)
-- Author: AI Assistant
-- Date: 2025-11-30

-- Add quality_score column (nullable, will be populated during generation)
ALTER TABLE document_sections 
ADD COLUMN IF NOT EXISTS quality_score FLOAT;

-- Add comment for documentation
COMMENT ON COLUMN document_sections.quality_score IS 'Overall quality score (0-100) from QualityValidator: weighted average of citation density (30%), academic tone (25%), coherence (25%), and word count accuracy (20%)';
