import { ProvenanceEvent, deriveQualityGateStatus, summarizeQualityEvidence } from '../provenance'

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
      unchecked: 0,
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
    expect(summary.checks.grammar.status).toBe('missing')
    expect(summary.checks.aiDetection.status).toBe('missing')
    expect(summary.sourcePack.status).toBe('missing')
    expect(summary.generation.sectionsGenerated).toBe(0)
  })

  it('summarizes the source pack: passed, warning (underfilled), failed (empty)', () => {
    const healthy = summarizeQualityEvidence([
      event(
        1,
        'source_pack_built',
        { pack_size: 18, mean_on_topic_score: 0.52, underfilled: false, bilingual: true },
        'retrieval'
      ),
    ])
    expect(healthy.sourcePack).toEqual({
      status: 'passed',
      packSize: 18,
      underfilled: false,
      bilingual: true,
    })

    const thin = summarizeQualityEvidence([
      event(
        1,
        'source_pack_built',
        { pack_size: 5, underfilled: true, bilingual: false },
        'retrieval'
      ),
    ])
    expect(thin.sourcePack.status).toBe('warning')
    expect(thin.sourcePack.underfilled).toBe(true)

    const empty = summarizeQualityEvidence([
      event(
        1,
        'source_pack_built',
        { pack_size: 0, underfilled: true, bilingual: false },
        'retrieval'
      ),
    ])
    expect(empty.sourcePack.status).toBe('failed')
    expect(empty.sourcePack.packSize).toBe(0)
  })

  it('prefers the rebuilt source pack event over the initial build', () => {
    const summary = summarizeQualityEvidence([
      event(
        1,
        'source_pack_built',
        { pack_size: 20, underfilled: false, bilingual: true },
        'retrieval'
      ),
      event(
        2,
        'source_pack_rebuilt',
        { pack_size: 4, underfilled: true, bilingual: true },
        'retrieval'
      ),
    ])
    expect(summary.sourcePack.status).toBe('warning')
    expect(summary.sourcePack.packSize).toBe(4)
  })

  it('surfaces unchecked checks from new-format events (GPTZero off case)', () => {
    const summary = summarizeQualityEvidence([
      event(1, 'quality_gate', {
        section_index: 1,
        passed: false,
        status: 'unchecked',
        checks: {
          grammar: { status: 'passed', score: 95 },
          plagiarism: { status: 'passed', score: 5 },
          ai_detection: {
            status: 'unchecked',
            score: null,
            reason: 'AI detection is disabled',
            provider: 'none',
          },
        },
        grammar_score: 95,
        plagiarism_score: 5,
        ai_detection_score: null,
        quality_score: 80,
      }),
    ])

    expect(summary.qualityGates.status).toBe('unchecked')
    expect(summary.qualityGates.unchecked).toBe(1)
    expect(summary.checks.grammar.status).toBe('passed')
    expect(summary.checks.plagiarism.status).toBe('passed')
    expect(summary.checks.aiDetection.status).toBe('unchecked')
    expect(summary.checks.aiDetection.unchecked).toBe(1)
  })

  it('reinterprets legacy fail-open events as unchecked, never passed', () => {
    // Legacy shape: passed=true but a null score (provider silently failed)
    const summary = summarizeQualityEvidence([
      event(1, 'quality_gate', {
        section_index: 1,
        passed: true,
        gates_enabled: true,
        grammar_score: null,
        plagiarism_score: 5,
        ai_detection_score: 20,
        quality_score: 80,
      }),
      // Legacy shape: gates disabled entirely
      event(2, 'quality_gate', {
        section_index: 2,
        passed: true,
        gates_enabled: false,
        grammar_score: 95,
        plagiarism_score: 5,
        ai_detection_score: 20,
        quality_score: 80,
      }),
    ])

    expect(summary.qualityGates.status).toBe('unchecked')
    expect(summary.qualityGates.unchecked).toBe(2)
    expect(summary.qualityGates.passed).toBe(0)
    expect(summary.checks.grammar.status).toBe('unchecked')
  })

  it('derives warning for mark_only citation gate with not_found sources', () => {
    // Legacy event: passed=true, no status key
    const legacy = summarizeQualityEvidence([
      event(
        1,
        'citation_gate',
        {
          passed: true,
          policy: 'mark_only',
          counts: { verified: 3, not_found: 2 },
          not_found_count: 2,
          not_found_titles: ['Phantom A', 'Phantom B'],
        },
        'verification'
      ),
    ])
    expect(legacy.citationGate.status).toBe('warning')

    // New event: explicit status wins
    const explicit = summarizeQualityEvidence([
      event(
        1,
        'citation_gate',
        {
          passed: true,
          status: 'warning',
          policy: 'mark_only',
          counts: { verified: 3, not_found: 1 },
          not_found_count: 1,
        },
        'verification'
      ),
    ])
    expect(explicit.citationGate.status).toBe('warning')
  })

  it('deriveQualityGateStatus mirrors the backend rule', () => {
    expect(deriveQualityGateStatus({ status: 'unchecked', passed: false })).toBe('unchecked')
    expect(deriveQualityGateStatus({ passed: false })).toBe('failed')
    expect(deriveQualityGateStatus({ passed: true, gates_enabled: false })).toBe('unchecked')
    expect(
      deriveQualityGateStatus({
        passed: true,
        grammar_score: null,
        plagiarism_score: 5,
        ai_detection_score: 20,
      })
    ).toBe('unchecked')
    expect(
      deriveQualityGateStatus({
        passed: true,
        gates_enabled: true,
        grammar_score: 95,
        plagiarism_score: 5,
        ai_detection_score: 20,
      })
    ).toBe('passed')
  })
})
