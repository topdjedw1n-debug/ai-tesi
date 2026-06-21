'use client'

import { useCallback, useEffect, useState } from 'react'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import { DocumentProvenance, ProvenanceEvent } from '@/lib/provenance'
import { LoadingSpinner } from '@/components/ui/LoadingSpinner'
import { formatDateTime } from '@/lib/utils/date'

interface ProvenanceTimelineProps {
  documentId: number
}

const STAGE_COLORS: Record<string, string> = {
  retrieval: 'bg-primary-500',
  outline: 'bg-primary-500',
  generation: 'bg-primary-500',
  quality: 'bg-amber-500',
  verification: 'bg-primary-500',
  export: 'bg-green-500',
}

const EVENT_LABELS: Record<string, string> = {
  rag_retrieved: 'Sources retrieved',
  section_generated: 'Section generated',
  humanized: 'Humanized',
  quality_gate: 'Quality gate',
  citation_gate: 'Citation gate',
  verification_summary: 'Citation verification',
  verification_error: 'Verification error',
  integrity_gate_failed: 'Integrity gate failed',
  integrity_report: 'Integrity report',
  exported: 'Exported',
}

const formatScore = (value: unknown): string =>
  typeof value === 'number' ? value.toFixed(1) : 'N/A'

const formatCounts = (counts: unknown): string => {
  if (!counts || typeof counts !== 'object') return '—'
  const entries = Object.entries(counts as Record<string, number>)
  if (entries.length === 0) return '—'
  return entries.map(([status, count]) => `${status}: ${count}`).join(', ')
}

function PassBadge({ passed }: { passed: boolean }) {
  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${
        passed ? 'bg-green-900 text-green-200' : 'bg-red-900 text-red-200'
      }`}
    >
      {passed ? 'Passed' : 'Failed'}
    </span>
  )
}

function EventDetails({ event }: { event: ProvenanceEvent }) {
  const payload = event.payload ?? {}

  switch (event.event_type) {
    case 'rag_retrieved':
      return (
        <p className="text-sm text-gray-300">
          Section {payload.section_index} &ldquo;{payload.section_title}&rdquo; ·{' '}
          {payload.sources_used ?? 0} sources retrieved
        </p>
      )

    case 'section_generated':
      return (
        <p className="text-sm text-gray-300">
          Section {payload.section_index} · {payload.model} ({payload.provider}) ·{' '}
          {(payload.word_count ?? 0).toLocaleString()} words · attempt{' '}
          {payload.attempts ?? 1}
        </p>
      )

    case 'humanized':
      return (
        <p className="text-sm text-gray-300">
          AI score {formatScore(payload.ai_score_before)}% →{' '}
          {formatScore(payload.ai_score_after)}% (threshold{' '}
          {formatScore(payload.threshold)}%)
          {payload.multi_pass ? ' · multi-pass' : ''}
        </p>
      )

    case 'quality_gate':
      return (
        <div className="space-y-1">
          <PassBadge passed={Boolean(payload.passed)} />
          {payload.passed ? (
            <p className="text-sm text-gray-300">
              Grammar {formatScore(payload.grammar_score)} · Plagiarism{' '}
              {formatScore(payload.plagiarism_score)}% · AI detection{' '}
              {formatScore(payload.ai_detection_score)}% · Quality{' '}
              {formatScore(payload.quality_score)}
            </p>
          ) : (
            <p className="text-sm text-red-400">{payload.detail}</p>
          )}
        </div>
      )

    case 'citation_gate':
      return (
        <div className="space-y-1">
          <PassBadge passed={Boolean(payload.passed)} />
          <p className="text-sm text-gray-300">
            Policy: {payload.policy ?? '—'} · {formatCounts(payload.counts)}
          </p>
          {Array.isArray(payload.not_found_titles) &&
            payload.not_found_titles.length > 0 && (
              <p className="text-sm text-red-400">
                Not found: {payload.not_found_titles.join('; ')}
              </p>
            )}
        </div>
      )

    case 'verification_summary':
      return (
        <p className="text-sm text-gray-300">
          {payload.total ?? 0} source(s) · {formatCounts(payload.counts)}
          {Array.isArray(payload.providers) && payload.providers.length > 0
            ? ` · via ${payload.providers.join(', ')}`
            : ''}
        </p>
      )

    case 'exported':
      return (
        <p className="text-sm text-gray-300">
          {Array.isArray(payload.formats) ? payload.formats.join(', ') : '—'}
          {typeof payload.file_size === 'number'
            ? ` · ${payload.file_size.toLocaleString()} bytes`
            : ''}
        </p>
      )

    case 'verification_error':
      return <p className="text-sm text-red-400">{payload.error}</p>

    default:
      return (
        <pre className="text-xs text-gray-400 whitespace-pre-wrap">
          {JSON.stringify(payload, null, 2)}
        </pre>
      )
  }
}

/**
 * Full provenance timeline of a document for the admin panel: every pipeline
 * event (retrieval, generation, quality gates, citation verification, export)
 * in chronological order with scores and gate outcomes.
 */
export function ProvenanceTimeline({ documentId }: ProvenanceTimelineProps) {
  const [events, setEvents] = useState<ProvenanceEvent[] | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchProvenance = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await apiClient.get<DocumentProvenance>(
        API_ENDPOINTS.DOCUMENTS.PROVENANCE(documentId)
      )
      setEvents(data?.events ?? [])
    } catch (error) {
      console.error('Failed to fetch document provenance:', error)
      setEvents(null)
    } finally {
      setIsLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    fetchProvenance()
  }, [fetchProvenance])

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-32">
        <LoadingSpinner />
      </div>
    )
  }

  if (!events || events.length === 0) {
    return <p className="text-gray-400">No provenance events recorded</p>
  }

  return (
    <ol className="relative space-y-4">
      {events.map((event, index) => (
        <li key={event.id} className="relative flex gap-4">
          {/* Timeline rail */}
          <div className="flex flex-col items-center">
            <span
              className={`h-3 w-3 rounded-full mt-1.5 flex-shrink-0 ${
                STAGE_COLORS[event.stage] ?? 'bg-gray-500'
              }`}
              aria-hidden="true"
            />
            {index < events.length - 1 && (
              <span className="w-px flex-1 bg-gray-700" aria-hidden="true" />
            )}
          </div>

          <div className="bg-gray-700 rounded p-4 flex-1 mb-1">
            <div className="flex items-center justify-between gap-4 mb-1">
              <div className="flex items-center gap-2">
                <span className="text-sm font-medium text-white">
                  {EVENT_LABELS[event.event_type] ?? event.event_type}
                </span>
                <span className="text-xs text-gray-400 uppercase tracking-wide">
                  {event.stage}
                </span>
              </div>
              <span className="text-xs text-gray-400 flex-shrink-0">
                {formatDateTime(event.created_at)}
              </span>
            </div>
            <EventDetails event={event} />
          </div>
        </li>
      ))}
    </ol>
  )
}
