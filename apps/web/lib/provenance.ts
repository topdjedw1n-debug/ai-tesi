/**
 * Document provenance ledger: types and pure helpers.
 *
 * Data source: GET /api/v1/documents/{id}/provenance
 * (chronological pipeline events written by the backend generation pipeline).
 *
 * CONTRACT: payload shapes are mirrored from the backend source of truth
 * apps/api/app/schemas/provenance.py (enforced there by shape tests).
 * If an event payload gains/loses/renames a key, update BOTH files together.
 */

// ============================================================================
// TYPES
// ============================================================================

export interface ProvenanceEvent {
  id: number
  stage: string
  event_type: string
  payload: Record<string, any> | null
  created_at: string | null
}

export interface DocumentProvenance {
  document_id: number
  total: number
  events: ProvenanceEvent[]
}

/** Verification status of a cited source (mirrors document_sources.verification_status) */
export type SourceStatus =
  | 'verified'
  | 'not_found'
  | 'mismatched'
  | 'failed' // unresolvable (provider outage / insufficient metadata)
  | 'unverified'

export interface SourceRecord {
  title: string
  authors: string[]
  year: number | null
  doi: string | null
  status: SourceStatus
}

export interface SourcesSummary {
  total: number
  verified: number
  /** Human-readable provider names, e.g. ['Crossref', 'OpenAlex'] */
  providers: string[]
}

export type GateStatus = 'passed' | 'failed' | 'missing'

export interface QualityEvidenceSummary {
  citationGate: {
    status: GateStatus
    policy: string | null
    total: number | null
    failedCount: number
  }
  qualityGates: {
    status: GateStatus
    passed: number
    failed: number
    total: number
  }
  claimVerification: {
    status: GateStatus
    checked: number
    unsupported: number
    uncertain: number
    total: number
  }
  reviewerPanel: {
    status: GateStatus
    passed: number
    failed: number
    total: number
    criticalOverrides: number
  }
  generation: {
    sectionsGenerated: number
    tokensUsed: number
    wordsGenerated: number
    providers: string[]
    models: string[]
  }
}

// ============================================================================
// HELPERS
// ============================================================================

const PROVIDER_LABELS: Record<string, string> = {
  crossref: 'Crossref',
  openalex: 'OpenAlex',
  semantic_scholar: 'Semantic Scholar',
  arxiv: 'arXiv',
}

const DEFAULT_PROVIDERS = ['Crossref', 'OpenAlex']

const normalizeStatus = (status: unknown): SourceStatus => {
  if (
    status === 'verified' ||
    status === 'not_found' ||
    status === 'mismatched' ||
    status === 'failed'
  ) {
    return status
  }
  return 'unverified'
}

const normalizeSource = (raw: Record<string, any>): SourceRecord => ({
  title: typeof raw.title === 'string' ? raw.title : '',
  authors: Array.isArray(raw.authors) ? raw.authors.filter((a) => typeof a === 'string') : [],
  year: typeof raw.year === 'number' ? raw.year : null,
  doi: typeof raw.doi === 'string' && raw.doi ? raw.doi : null,
  status: normalizeStatus(raw.status ?? raw.verification_status),
})

const latestEventOfType = (
  events: ProvenanceEvent[],
  eventType: string
): ProvenanceEvent | undefined => {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].event_type === eventType) return events[i]
  }
  return undefined
}

/**
 * Extract the cited sources with their final verification statuses.
 *
 * Prefers the latest verification_summary event (per-source statuses after
 * verification). Falls back to deduplicated rag_retrieved sources (status
 * 'unverified') for documents where verification has not run.
 */
export function extractSources(events: ProvenanceEvent[]): SourceRecord[] {
  const summary = latestEventOfType(events, 'verification_summary')
  const summarySources = summary?.payload?.sources
  if (Array.isArray(summarySources) && summarySources.length > 0) {
    return summarySources.map(normalizeSource)
  }

  // Fallback: collect sources from rag_retrieved events, dedup by DOI or title+year
  const seen = new Set<string>()
  const sources: SourceRecord[] = []
  for (const event of events) {
    if (event.event_type !== 'rag_retrieved') continue
    const eventSources = event.payload?.sources
    if (!Array.isArray(eventSources)) continue
    for (const raw of eventSources) {
      const source = normalizeSource(raw)
      if (!source.title) continue
      const key = source.doi
        ? `doi:${source.doi.toLowerCase()}`
        : `title:${source.title.toLowerCase()}|${source.year ?? ''}`
      if (seen.has(key)) continue
      seen.add(key)
      sources.push(source)
    }
  }
  return sources
}

/**
 * Build the banner summary: "27/29 sources verified via Crossref/OpenAlex".
 */
export function summarizeSources(
  events: ProvenanceEvent[],
  sources: SourceRecord[]
): SourcesSummary {
  const summary = latestEventOfType(events, 'verification_summary')
  const rawProviders = summary?.payload?.providers
  const providers =
    Array.isArray(rawProviders) && rawProviders.length > 0
      ? rawProviders.map((p: string) => PROVIDER_LABELS[p] ?? p)
      : DEFAULT_PROVIDERS

  return {
    total: sources.length,
    verified: sources.filter((s) => s.status === 'verified').length,
    providers,
  }
}

const gateStatus = (passed: boolean | null): GateStatus => {
  if (passed === null) return 'missing'
  return passed ? 'passed' : 'failed'
}

const numberOrZero = (value: unknown): number =>
  typeof value === 'number' && Number.isFinite(value) ? value : 0

const uniqueStrings = (values: unknown[]): string[] =>
  Array.from(
    new Set(values.filter((value): value is string => typeof value === 'string' && value.length > 0))
  )

/**
 * Summarize the provenance ledger into the minimum manager-facing evidence
 * needed for the Phase 1 QA proof run.
 */
export function summarizeQualityEvidence(events: ProvenanceEvent[]): QualityEvidenceSummary {
  const citationGate = latestEventOfType(events, 'citation_gate')
  const citationPayload = citationGate?.payload ?? null
  const citationCounts = citationPayload?.counts
  const citationFailedCount =
    numberOrZero(citationPayload?.not_found_count) +
    (citationCounts && typeof citationCounts === 'object'
      ? numberOrZero((citationCounts as Record<string, unknown>).mismatched) +
        numberOrZero((citationCounts as Record<string, unknown>).failed)
      : 0)

  const qualityGateEvents = events.filter((event) => event.event_type === 'quality_gate')
  const qualityPassed = qualityGateEvents.filter((event) => event.payload?.passed === true).length
  const qualityFailed = qualityGateEvents.filter((event) => event.payload?.passed === false).length

  const claimSummary = latestEventOfType(events, 'claim_check_summary')
  const claimCounts = claimSummary?.payload?.counts
  const unsupportedClaims =
    claimCounts && typeof claimCounts === 'object'
      ? numberOrZero((claimCounts as Record<string, unknown>).unsupported)
      : 0
  const uncertainClaims =
    claimCounts && typeof claimCounts === 'object'
      ? numberOrZero((claimCounts as Record<string, unknown>).uncertain)
      : 0

  const panelEvents = events.filter(
    (event) => event.event_type === 'panel_review' || event.event_type === 'panel_gate_failed'
  )
  const panelPassed = panelEvents.filter((event) => event.payload?.passed === true).length
  const panelFailed = panelEvents.filter(
    (event) => event.event_type === 'panel_gate_failed' || event.payload?.passed === false
  ).length
  const criticalOverrides = panelEvents.filter((event) => event.payload?.critical_override === true).length

  const sectionEvents = events.filter((event) => event.event_type === 'section_generated')
  const tokensUsed = sectionEvents.reduce(
    (total, event) => total + numberOrZero(event.payload?.tokens_used),
    0
  )
  const wordsGenerated = sectionEvents.reduce(
    (total, event) => total + numberOrZero(event.payload?.word_count),
    0
  )

  return {
    citationGate: {
      status: gateStatus(typeof citationPayload?.passed === 'boolean' ? citationPayload.passed : null),
      policy: typeof citationPayload?.policy === 'string' ? citationPayload.policy : null,
      total: typeof citationPayload?.total === 'number' ? citationPayload.total : null,
      failedCount: citationFailedCount,
    },
    qualityGates: {
      status:
        qualityGateEvents.length === 0
          ? 'missing'
          : qualityFailed > 0
            ? 'failed'
            : 'passed',
      passed: qualityPassed,
      failed: qualityFailed,
      total: qualityGateEvents.length,
    },
    claimVerification: {
      status: !claimSummary
        ? 'missing'
        : unsupportedClaims > 0
          ? 'failed'
          : 'passed',
      checked: numberOrZero(claimSummary?.payload?.checked),
      unsupported: unsupportedClaims,
      uncertain: uncertainClaims,
      total: numberOrZero(claimSummary?.payload?.total_claims),
    },
    reviewerPanel: {
      status:
        panelEvents.length === 0
          ? 'missing'
          : panelFailed > 0 || criticalOverrides > 0
            ? 'failed'
            : 'passed',
      passed: panelPassed,
      failed: panelFailed,
      total: panelEvents.length,
      criticalOverrides,
    },
    generation: {
      sectionsGenerated: sectionEvents.length,
      tokensUsed,
      wordsGenerated,
      providers: uniqueStrings(sectionEvents.map((event) => event.payload?.provider)),
      models: uniqueStrings(sectionEvents.map((event) => event.payload?.model)),
    },
  }
}

/** Build a clickable DOI URL */
export function doiUrl(doi: string): string {
  return `https://doi.org/${encodeURIComponent(doi).replace(/%2F/gi, '/')}`
}
