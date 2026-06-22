import { ProvenanceEvent, summarizeQualityEvidence } from '../provenance'

const event = (
  id: number,
  event_type: string,
  payload: Record<string, any>,
  stage = 'quality'
): ProvenanceEvent => ({
  id,
  stage,
  event_type,
  payload,
  created_at: '2026-06-22T00:00:00Z',
})

describe('provenance quality evidence helpers', () => {
  it('summarizes Phase 1 manager evidence from provenance events', () => {
    const summary = summarizeQualityEvidence([
      event(
        1,
        'section_generated',
        {
          section_index: 1,
          section_title: 'Introduction',
          provider: 'openai',
          model: 'gpt-4',
          word_count: 1200,
          tokens_used: 2500,
          attempts: 1,
        },
        'generation'
      ),
      event(
        2,
        'section_generated',
        {
          section_index: 2,
          section_title: 'Methods',
          provider: 'openai',
          model: 'gpt-4',
          word_count: 900,
          tokens_used: 1700,
          attempts: 1,
        },
        'generation'
      ),
      event(3, 'quality_gate', {
        section_index: 1,
        passed: true,
        grammar_score: 95,
        plagiarism_score: 3,
        ai_detection_score: 22,
        quality_score: 88,
      }),
      event(4, 'quality_gate', {
        section_index: 2,
        passed: false,
        detail: 'AI detection remained above threshold',
      }),
      event(
        5,
        'citation_gate',
        {
          passed: false,
          policy: 'strict',
          total: 3,
          not_found_count: 1,
          counts: { verified: 2, not_found: 1, mismatched: 0, failed: 0 },
        },
        'verification'
      ),
      event(
        6,
        'claim_check_summary',
        {
          total_claims: 8,
          checked: 8,
          counts: { supported: 6, unsupported: 1, uncertain: 1 },
          budget: 50,
          budget_exhausted: false,
        },
        'verification'
      ),
      event(7, 'panel_review', {
        section_index: 1,
        passed: true,
        critical_override: false,
        attempts: 1,
      }),
      event(8, 'panel_gate_failed', {
        section_index: 2,
        passed: false,
        critical_override: true,
        attempts: 2,
      }),
    ])

    expect(summary.generation).toEqual({
      sectionsGenerated: 2,
      tokensUsed: 4200,
      wordsGenerated: 2100,
      providers: ['openai'],
      models: ['gpt-4'],
    })
    expect(summary.citationGate).toEqual({
      status: 'failed',
      policy: 'strict',
      total: 3,
      failedCount: 1,
    })
    expect(summary.qualityGates).toEqual({
      status: 'failed',
      passed: 1,
      failed: 1,
      total: 2,
    })
    expect(summary.claimVerification).toEqual({
      status: 'failed',
      checked: 8,
      unsupported: 1,
      uncertain: 1,
      total: 8,
    })
    expect(summary.reviewerPanel).toEqual({
      status: 'failed',
      passed: 1,
      failed: 1,
      total: 2,
      criticalOverrides: 1,
    })
  })

  it('marks unavailable gates as missing instead of passed', () => {
    const summary = summarizeQualityEvidence([])

    expect(summary.citationGate.status).toBe('missing')
    expect(summary.qualityGates.status).toBe('missing')
    expect(summary.claimVerification.status).toBe('missing')
    expect(summary.reviewerPanel.status).toBe('missing')
    expect(summary.generation.sectionsGenerated).toBe(0)
  })
})
