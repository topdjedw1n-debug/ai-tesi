-- Add AI detection score to document_sections
-- Date: 2025-11-30
-- Purpose: Track AI-generated content probability for quality control

-- Add ai_detection_score column (0-100, lower is better = more human-like)
ALTER TABLE document_sections
ADD COLUMN IF NOT EXISTS ai_detection_score FLOAT NULL;

-- Add comment for documentation
COMMENT ON COLUMN document_sections.ai_detection_score IS 
'AI detection probability (0-100, lower is better = more human-like). NULL if not checked. Threshold: 55% (target: <50%).';
