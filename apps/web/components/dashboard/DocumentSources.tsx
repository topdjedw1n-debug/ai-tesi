'use client'

import { useCallback, useEffect, useState } from 'react'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import {
  DocumentProvenance,
  SourceRecord,
  SourceStatus,
  SourcesSummary,
  doiUrl,
  extractSources,
  summarizeSources,
} from '@/lib/provenance'
import {
  CheckCircleIcon,
  XCircleIcon,
  QuestionMarkCircleIcon,
  ShieldCheckIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline'

interface DocumentSourcesProps {
  documentId: number
}

const STATUS_CONFIG: Record<
  SourceStatus,
  { label: string; badgeClass: string; Icon: typeof CheckCircleIcon; iconClass: string }
> = {
  verified: {
    label: 'Verified',
    badgeClass: 'bg-green-100 text-green-800',
    Icon: CheckCircleIcon,
    iconClass: 'text-green-500',
  },
  not_found: {
    label: 'Not found',
    badgeClass: 'bg-red-100 text-red-800',
    Icon: XCircleIcon,
    iconClass: 'text-red-500',
  },
  mismatched: {
    label: 'Mismatched',
    badgeClass: 'bg-amber-100 text-amber-800',
    Icon: QuestionMarkCircleIcon,
    iconClass: 'text-amber-500',
  },
  failed: {
    label: 'Unverifiable',
    badgeClass: 'bg-amber-100 text-amber-800',
    Icon: QuestionMarkCircleIcon,
    iconClass: 'text-amber-500',
  },
  unverified: {
    label: 'Pending',
    badgeClass: 'bg-gray-100 text-gray-800',
    Icon: QuestionMarkCircleIcon,
    iconClass: 'text-gray-400',
  },
}

function SourceRow({ source }: { source: SourceRecord }) {
  const config = STATUS_CONFIG[source.status]
  const { Icon } = config
  const meta = [source.authors.join(', '), source.year?.toString()]
    .filter(Boolean)
    .join(' · ')

  return (
    <li className="flex items-start gap-3 py-3">
      <Icon
        className={`h-5 w-5 mt-0.5 flex-shrink-0 ${config.iconClass}`}
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-gray-900">{source.title}</p>
        {meta && <p className="mt-0.5 text-sm text-gray-500">{meta}</p>}
        {source.doi && (
          <a
            href={doiUrl(source.doi)}
            target="_blank"
            rel="noopener noreferrer"
            className="mt-0.5 inline-block text-sm text-primary-600 hover:text-primary-800 hover:underline break-all"
          >
            {source.doi}
          </a>
        )}
      </div>
      <span
        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ${config.badgeClass}`}
      >
        {config.label}
      </span>
    </li>
  )
}

function VerificationBanner({ summary }: { summary: SourcesSummary }) {
  const allVerified = summary.total > 0 && summary.verified === summary.total
  const BannerIcon = allVerified ? ShieldCheckIcon : ShieldExclamationIcon

  return (
    <div
      data-testid="sources-banner"
      className={`flex items-center gap-3 rounded-lg p-4 ${
        allVerified ? 'bg-green-50 text-green-800' : 'bg-amber-50 text-amber-800'
      }`}
    >
      <BannerIcon className="h-6 w-6 flex-shrink-0" aria-hidden="true" />
      <p className="text-sm font-medium">
        {summary.verified}/{summary.total} sources verified via{' '}
        {summary.providers.join(', ')}
      </p>
    </div>
  )
}

/**
 * "Sources certificate" section for the document page: every cited source
 * with its verification status, plus a summary banner.
 *
 * Renders nothing when the document has no provenance data (legacy documents
 * or generation not finished yet).
 */
export function DocumentSources({ documentId }: DocumentSourcesProps) {
  const [sources, setSources] = useState<SourceRecord[] | null>(null)
  const [summary, setSummary] = useState<SourcesSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchProvenance = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await apiClient.get<DocumentProvenance>(
        API_ENDPOINTS.DOCUMENTS.PROVENANCE(documentId)
      )
      const events = data?.events ?? []
      const extracted = extractSources(events)
      setSources(extracted)
      setSummary(summarizeSources(events, extracted))
    } catch (error) {
      // Auxiliary section: fail silently, the rest of the page still works
      console.error('Failed to fetch document provenance:', error)
      setSources(null)
      setSummary(null)
    } finally {
      setIsLoading(false)
    }
  }, [documentId])

  useEffect(() => {
    fetchProvenance()
  }, [fetchProvenance])

  if (isLoading) {
    return (
      <div className="bg-white shadow rounded-lg p-6">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Sources</h2>
        <div className="space-y-3 animate-pulse">
          <div className="h-12 bg-gray-100 rounded-lg" />
          <div className="h-10 bg-gray-100 rounded" />
          <div className="h-10 bg-gray-100 rounded" />
        </div>
      </div>
    )
  }

  if (!sources || sources.length === 0 || !summary) {
    return null
  }

  return (
    <div className="bg-white shadow rounded-lg p-6">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Sources</h2>
      <VerificationBanner summary={summary} />
      <ul className="mt-2 divide-y divide-gray-100">
        {sources.map((source, index) => (
          <SourceRow key={source.doi ?? `${source.title}-${index}`} source={source} />
        ))}
      </ul>
    </div>
  )
}
