'use client'

import type React from 'react'
import {
  ClockIcon,
  CurrencyEuroIcon,
  DocumentTextIcon,
  ExclamationTriangleIcon,
  NoSymbolIcon,
  ShieldExclamationIcon,
} from '@heroicons/react/24/outline'

export type RiskTone = 'critical' | 'warning' | 'missing' | 'ok'

export interface ProductionRiskCard {
  id: string
  label: string
  value: number | string
  detail: string
  tone: RiskTone
  Icon: React.ComponentType<{ className?: string }>
}

export interface ProductionRiskSnapshot {
  openDocuments: number
  activeJobs: number
  stuckJobs: number
  failedQaCount: number
  qaAggregationAvailable: boolean
  deadlineRiskAvailable: boolean
  readyForReleaseAvailable: boolean
  tokenCostTodayCents: number
  tokensToday: number
}

interface StatsGridProps {
  snapshot: ProductionRiskSnapshot
}

const toneClasses: Record<RiskTone, { card: string; icon: string; value: string }> = {
  critical: {
    card: 'border-red-900/50 bg-red-950/30',
    icon: 'bg-red-900/70 text-red-200',
    value: 'text-red-100',
  },
  warning: {
    card: 'border-amber-900/50 bg-amber-950/20',
    icon: 'bg-amber-800/70 text-amber-100',
    value: 'text-amber-100',
  },
  missing: {
    card: 'border-gray-700 bg-gray-800',
    icon: 'bg-gray-700 text-gray-200',
    value: 'text-gray-100',
  },
  ok: {
    card: 'border-primary-900/50 bg-primary-950/20',
    icon: 'bg-primary-800/70 text-primary-100',
    value: 'text-primary-100',
  },
}

const formatCurrency = (cents: number): string =>
  `EUR ${(Math.max(0, cents) / 100).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`

export function buildProductionRiskCards(
  snapshot: ProductionRiskSnapshot
): ProductionRiskCard[] {
  return [
    {
      id: 'open-documents',
      label: 'Open cases/documents',
      value: snapshot.openDocuments,
      detail: `${snapshot.activeJobs} active generation job(s). ProductionCase layer is not wired yet.`,
      tone: snapshot.openDocuments > 0 || snapshot.activeJobs > 0 ? 'warning' : 'ok',
      Icon: DocumentTextIcon,
    },
    {
      id: 'stuck-jobs',
      label: 'Stuck jobs',
      value: snapshot.stuckJobs,
      detail:
        snapshot.stuckJobs > 0
          ? 'Generation needs cleanup or manual retry.'
          : 'No stuck queued/running jobs detected by the admin monitor.',
      tone: snapshot.stuckJobs > 0 ? 'critical' : 'ok',
      Icon: ClockIcon,
    },
    {
      id: 'failed-qa',
      label: 'Failed QA / no-data QA',
      value: snapshot.qaAggregationAvailable
        ? snapshot.failedQaCount
        : snapshot.failedQaCount > 0
          ? `${snapshot.failedQaCount} failed + No data`
          : 'No data',
      detail: snapshot.qaAggregationAvailable
        ? `${snapshot.failedQaCount} failed_quality document(s) in the current admin sample.`
        : 'No aggregate QA gate endpoint yet. Missing evidence is not treated as passed.',
      tone: snapshot.failedQaCount > 0 ? 'critical' : 'missing',
      Icon: ShieldExclamationIcon,
    },
    {
      id: 'deadline-risk',
      label: 'Deadline risk',
      value: snapshot.deadlineRiskAvailable ? 0 : 'No data',
      detail: snapshot.deadlineRiskAvailable
        ? 'No deadline risk detected.'
        : 'ProductionCase.deadline_at is not implemented yet.',
      tone: snapshot.deadlineRiskAvailable ? 'ok' : 'missing',
      Icon: ExclamationTriangleIcon,
    },
    {
      id: 'ready-release',
      label: 'Ready for release',
      value: snapshot.readyForReleaseAvailable ? 0 : 'No data',
      detail: snapshot.readyForReleaseAvailable
        ? 'No documents are waiting for release review.'
        : 'ReleaseGateResult and release_status are not implemented yet.',
      tone: snapshot.readyForReleaseAvailable ? 'ok' : 'missing',
      Icon: NoSymbolIcon,
    },
    {
      id: 'token-cost',
      label: 'Token cost today',
      value: formatCurrency(snapshot.tokenCostTodayCents),
      detail: `${snapshot.tokensToday.toLocaleString()} token(s) recorded today.`,
      tone: snapshot.tokenCostTodayCents > 0 ? 'warning' : 'ok',
      Icon: CurrencyEuroIcon,
    },
  ]
}

export function StatsGrid({ snapshot }: StatsGridProps) {
  const cards = buildProductionRiskCards(snapshot)

  return (
    <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3">
      {cards.map(({ id, label, value, detail, tone, Icon }) => {
        const classes = toneClasses[tone]

        return (
          <section
            key={id}
            className={`rounded-lg border p-5 shadow-sm ${classes.card}`}
            aria-label={label}
          >
            <div className="flex items-start justify-between gap-4">
              <div className="min-w-0">
                <p className="text-sm font-medium text-gray-400">{label}</p>
                <p className={`mt-2 font-mono text-2xl font-semibold ${classes.value}`}>
                  {typeof value === 'number' ? value.toLocaleString() : value}
                </p>
              </div>
              <div className={`rounded-md p-2 ${classes.icon}`}>
                <Icon className="h-5 w-5" aria-hidden="true" />
              </div>
            </div>
            <p className="mt-3 text-sm leading-5 text-gray-400">{detail}</p>
          </section>
        )
      })}
    </div>
  )
}
