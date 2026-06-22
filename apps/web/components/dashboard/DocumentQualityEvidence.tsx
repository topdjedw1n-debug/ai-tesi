'use client'

import { useCallback, useEffect, useState } from 'react'
import { apiClient, API_ENDPOINTS } from '@/lib/api'
import {
  DocumentProvenance,
  GateStatus,
  QualityEvidenceSummary,
  summarizeQualityEvidence,
} from '@/lib/provenance'
import {
  CheckCircleIcon,
  ExclamationTriangleIcon,
  QuestionMarkCircleIcon,
  ShieldCheckIcon,
} from '@heroicons/react/24/outline'

interface DocumentQualityEvidenceProps {
  documentId: number
}

const STATUS_CONFIG: Record<
  GateStatus,
  { label: string; badgeClass: string; Icon: typeof CheckCircleIcon; iconClass: string }
> = {
  passed: {
    label: 'Passed',
    badgeClass: 'bg-green-100 text-green-800',
    Icon: CheckCircleIcon,
    iconClass: 'text-green-500',
  },
  failed: {
    label: 'Needs review',
    badgeClass: 'bg-red-100 text-red-800',
    Icon: ExclamationTriangleIcon,
    iconClass: 'text-red-500',
  },
  missing: {
    label: 'No data',
    badgeClass: 'bg-gray-100 text-gray-800',
    Icon: QuestionMarkCircleIcon,
    iconClass: 'text-gray-400',
  },
}

function EvidenceRow({
  title,
  status,
  detail,
}: {
  title: string
  status: GateStatus
  detail: string
}) {
  const config = STATUS_CONFIG[status]
  const { Icon } = config

  return (
    <li className="flex items-start gap-3 py-3">
      <Icon className={`h-5 w-5 mt-0.5 flex-shrink-0 ${config.iconClass}`} aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium text-gray-900">{title}</p>
        <p className="mt-0.5 text-sm text-gray-500">{detail}</p>
      </div>
      <span
        className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium flex-shrink-0 ${config.badgeClass}`}
      >
        {config.label}
      </span>
    </li>
  )
}

function formatNumber(value: number): string {
  return value.toLocaleString()
}

function buildRows(summary: QualityEvidenceSummary) {
  return [
    {
      title: 'Citation gate',
      status: summary.citationGate.status,
      detail:
        summary.citationGate.status === 'missing'
          ? 'Citation verification has not emitted a gate event yet.'
          : `${summary.citationGate.total ?? 0} sources checked · ${summary.citationGate.failedCount} need review · policy ${summary.citationGate.policy ?? 'unknown'}`,
    },
    {
      title: 'Section quality gates',
      status: summary.qualityGates.status,
      detail:
        summary.qualityGates.status === 'missing'
          ? 'No quality gate events are available for this document.'
          : `${summary.qualityGates.passed}/${summary.qualityGates.total} passed · ${summary.qualityGates.failed} failed`,
    },
    {
      title: 'Claim support',
      status: summary.claimVerification.status,
      detail:
        summary.claimVerification.status === 'missing'
          ? 'Claim verification is unavailable or not enabled for this run.'
          : `${summary.claimVerification.checked}/${summary.claimVerification.total} checked · ${summary.claimVerification.unsupported} unsupported · ${summary.claimVerification.uncertain} uncertain`,
    },
    {
      title: 'Reviewer panel',
      status: summary.reviewerPanel.status,
      detail:
        summary.reviewerPanel.status === 'missing'
          ? 'Reviewer panel is unavailable or not enabled for this run.'
          : `${summary.reviewerPanel.passed}/${summary.reviewerPanel.total} passed · ${summary.reviewerPanel.failed} failed · ${summary.reviewerPanel.criticalOverrides} critical overrides`,
    },
    {
      title: 'External detectors',
      status: 'missing' as GateStatus,
      detail: 'Record plagiarism and AI-risk detector results in the Phase 1 run report before delivery.',
    },
  ]
}

/**
 * Manager-facing QA evidence card for the Phase 1 internal proof loop.
 * It intentionally summarizes existing provenance data instead of creating a
 * second QA contract. Manual detector outcomes stay in the run report until an
 * automated provider is wired into the pipeline.
 */
export function DocumentQualityEvidence({ documentId }: DocumentQualityEvidenceProps) {
  const [summary, setSummary] = useState<QualityEvidenceSummary | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const fetchProvenance = useCallback(async () => {
    try {
      setIsLoading(true)
      const data = await apiClient.get<DocumentProvenance>(
        API_ENDPOINTS.DOCUMENTS.PROVENANCE(documentId)
      )
      setSummary(summarizeQualityEvidence(data?.events ?? []))
    } catch (error) {
      console.error('Failed to fetch quality evidence:', error)
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
      <div className="bg-white shadow rounded-lg p-6" data-testid="quality-evidence-loading">
        <h2 className="text-lg font-semibold text-gray-900 mb-4">QA Evidence</h2>
        <div className="space-y-3 animate-pulse">
          <div className="h-10 bg-gray-100 rounded" />
          <div className="h-10 bg-gray-100 rounded" />
          <div className="h-10 bg-gray-100 rounded" />
        </div>
      </div>
    )
  }

  if (!summary) return null

  const models = summary.generation.models.length > 0 ? summary.generation.models.join(', ') : 'unknown model'
  const providers =
    summary.generation.providers.length > 0 ? summary.generation.providers.join(', ') : 'unknown provider'

  return (
    <div className="bg-white shadow rounded-lg p-6" data-testid="quality-evidence">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">QA Evidence</h2>
          <p className="mt-1 text-sm text-gray-500">
            Internal manager proof for Phase 1 release decisions.
          </p>
        </div>
        <ShieldCheckIcon className="h-6 w-6 text-primary-500 flex-shrink-0" aria-hidden="true" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Sections</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {formatNumber(summary.generation.sectionsGenerated)}
          </p>
        </div>
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Words</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {formatNumber(summary.generation.wordsGenerated)}
          </p>
        </div>
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Tokens</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {formatNumber(summary.generation.tokensUsed)}
          </p>
        </div>
      </div>

      <p className="mt-3 text-xs text-gray-500">
        Generated with {models} via {providers}.
      </p>

      <ul className="mt-3 divide-y divide-gray-100">
        {buildRows(summary).map((row) => (
          <EvidenceRow key={row.title} {...row} />
        ))}
      </ul>
    </div>
  )
}
