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
    label: 'Пройдено',
    badgeClass: 'bg-green-100 text-green-800',
    Icon: CheckCircleIcon,
    iconClass: 'text-green-500',
  },
  failed: {
    label: 'Потребує уваги',
    badgeClass: 'bg-red-100 text-red-800',
    Icon: ExclamationTriangleIcon,
    iconClass: 'text-red-500',
  },
  warning: {
    label: 'Попередження',
    badgeClass: 'bg-amber-100 text-amber-800',
    Icon: ExclamationTriangleIcon,
    iconClass: 'text-amber-500',
  },
  unchecked: {
    label: 'Не перевірено',
    badgeClass: 'bg-amber-100 text-amber-800',
    Icon: QuestionMarkCircleIcon,
    iconClass: 'text-amber-500',
  },
  missing: {
    label: 'Немає даних',
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

function checkDetail(check: QualityEvidenceSummary['checks']['grammar']): string {
  if (check.status === 'missing') return 'По цій роботі немає записів перевірок якості.'
  if (check.status === 'unchecked') {
    return `Не перевірено на ${check.unchecked}/${check.total} розділах — перевірка вимкнена або недоступна.`
  }
  return `${check.passed}/${check.total} пройдено · ${check.failed} провалено · ${check.unchecked} не перевірено`
}

function sourcePackDetail(sourcePack: QualityEvidenceSummary['sourcePack']): string {
  if (sourcePack.status === 'missing') {
    return 'Пак джерел для цього прогону не записано (grounding вимкнено або стара робота).'
  }
  if (sourcePack.status === 'failed') {
    return 'Пак джерел порожній — генерація йшла без опори на джерела.'
  }
  const bilingual = sourcePack.bilingual ? ' · двомовний пошук' : ''
  if (sourcePack.status === 'warning') {
    return `${sourcePack.packSize} джерел — поріг релевантності було послаблено, переглянь джерела${bilingual}`
  }
  return `${sourcePack.packSize} джерел за темою у паку${bilingual}`
}

function buildRows(summary: QualityEvidenceSummary) {
  return [
    {
      title: 'Наявність джерел',
      status: summary.sourcePack.status,
      detail: sourcePackDetail(summary.sourcePack),
    },
    {
      title: 'Перевірка цитат',
      status: summary.citationGate.status,
      detail:
        summary.citationGate.status === 'missing'
          ? 'Верифікація цитат ще не залишила запису по цій роботі.'
          : `${summary.citationGate.total ?? 0} джерел перевірено · ${summary.citationGate.failedCount} потребують уваги · політика ${summary.citationGate.policy ?? 'невідома'}`,
    },
    {
      title: 'Якість розділів',
      status: summary.qualityGates.status,
      detail:
        summary.qualityGates.status === 'missing'
          ? 'По цій роботі немає записів перевірок якості.'
          : `${summary.qualityGates.passed}/${summary.qualityGates.total} пройдено · ${summary.qualityGates.failed} провалено · ${summary.qualityGates.unchecked} не перевірено`,
    },
    {
      title: 'Граматика',
      status: summary.checks.grammar.status,
      detail: checkDetail(summary.checks.grammar),
    },
    {
      title: 'Плагіат',
      status: summary.checks.plagiarism.status,
      detail: checkDetail(summary.checks.plagiarism),
    },
    {
      title: 'AI-детектор',
      status: summary.checks.aiDetection.status,
      detail: checkDetail(summary.checks.aiDetection),
    },
    {
      title: 'Підкріпленість тверджень',
      status: summary.claimVerification.status,
      detail:
        summary.claimVerification.status === 'missing'
          ? 'Перевірка тверджень недоступна або вимкнена для цього прогону.'
          : `${summary.claimVerification.checked}/${summary.claimVerification.total} перевірено · ${summary.claimVerification.unsupported} без опори · ${summary.claimVerification.uncertain} непевних`,
    },
    {
      title: 'Панель рецензентів',
      status: summary.reviewerPanel.status,
      detail:
        summary.reviewerPanel.status === 'missing'
          ? 'Панель рецензентів недоступна або вимкнена для цього прогону.'
          : `${summary.reviewerPanel.passed}/${summary.reviewerPanel.total} пройдено · ${summary.reviewerPanel.failed} провалено · ${summary.reviewerPanel.criticalOverrides} критичних override`,
    },
    {
      title: 'Зовнішні детектори',
      status: 'missing' as GateStatus,
      detail: 'Результати зовнішніх перевірок (плагіат, AI-ризик) фіксуються у звіті прогону перед видачею.',
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
        <h2 className="text-lg font-semibold text-gray-900 mb-4">Докази якості</h2>
        <div className="space-y-3 animate-pulse">
          <div className="h-10 bg-gray-100 rounded" />
          <div className="h-10 bg-gray-100 rounded" />
          <div className="h-10 bg-gray-100 rounded" />
        </div>
      </div>
    )
  }

  if (!summary) return null

  const models = summary.generation.models.length > 0 ? summary.generation.models.join(', ') : 'невідома модель'
  const providers =
    summary.generation.providers.length > 0 ? summary.generation.providers.join(', ') : 'невідомий провайдер'

  return (
    <div className="bg-white shadow rounded-lg p-6" data-testid="quality-evidence">
      <div className="flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-gray-900">Докази якості</h2>
          <p className="mt-1 text-sm text-gray-500">
            Причини довіряти чи не довіряти цій роботі перед видачею
          </p>
        </div>
        <ShieldCheckIcon className="h-6 w-6 text-primary-500 flex-shrink-0" aria-hidden="true" />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Розділів</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {formatNumber(summary.generation.sectionsGenerated)}
          </p>
        </div>
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Слів</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {formatNumber(summary.generation.wordsGenerated)}
          </p>
        </div>
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-xs font-medium uppercase tracking-wide text-gray-500">Токенів</p>
          <p className="mt-1 text-lg font-semibold text-gray-900">
            {formatNumber(summary.generation.tokensUsed)}
          </p>
        </div>
      </div>

      <p className="mt-3 text-xs text-gray-500">
        Згенеровано моделлю {models} ({providers}).
      </p>

      <ul className="mt-3 divide-y divide-gray-100">
        {buildRows(summary).map((row) => (
          <EvidenceRow key={row.title} {...row} />
        ))}
      </ul>
    </div>
  )
}
