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

/** Build a clickable DOI URL */
export function doiUrl(doi: string): string {
  return `https://doi.org/${encodeURIComponent(doi).replace(/%2F/gi, '/')}`
}
