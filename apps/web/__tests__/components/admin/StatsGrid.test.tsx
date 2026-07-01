/**
 * Tests for the admin production-risk grid.
 */

import { render, screen } from '@testing-library/react'
import {
  buildProductionRiskCards,
  ProductionRiskSnapshot,
  StatsGrid,
} from '@/components/admin/dashboard/StatsGrid'

const riskSnapshot: ProductionRiskSnapshot = {
  openDocuments: 7,
  activeJobs: 2,
  stuckJobs: 1,
  failedQaCount: 3,
  qaAggregationAvailable: false,
  deadlineRiskAvailable: false,
  readyForReleaseAvailable: false,
  tokenCostTodayCents: 1234,
  tokensToday: 45678,
}

describe('StatsGrid production risk', () => {
  it('puts production risk cards first instead of SaaS vanity metrics', () => {
    render(<StatsGrid snapshot={riskSnapshot} />)

    expect(screen.getByText('Open cases/documents')).toBeInTheDocument()
    expect(screen.getByText('Stuck jobs')).toBeInTheDocument()
    expect(screen.getByText('Failed QA / no-data QA')).toBeInTheDocument()
    expect(screen.getByText('Deadline risk')).toBeInTheDocument()
    expect(screen.getByText('Ready for release')).toBeInTheDocument()
    expect(screen.getByText('Token cost today')).toBeInTheDocument()

    expect(screen.queryByText('MRR')).not.toBeInTheDocument()
    expect(screen.queryByText('ARPU')).not.toBeInTheDocument()
    expect(screen.queryByText('Churn Rate')).not.toBeInTheDocument()
  })

  it('shows missing QA aggregation as no data instead of passed', () => {
    const cards = buildProductionRiskCards(riskSnapshot)
    const qaCard = cards.find((card) => card.id === 'failed-qa')

    expect(qaCard).toMatchObject({
      value: '3 failed + No data',
      tone: 'critical',
    })
    expect(qaCard?.detail).toContain('Missing evidence is not treated as passed')
  })

  it('marks deadline and release readiness as missing until production cases exist', () => {
    render(<StatsGrid snapshot={riskSnapshot} />)

    expect(screen.getByText('ProductionCase.deadline_at is not implemented yet.')).toBeInTheDocument()
    expect(screen.getByText('ReleaseGateResult and release_status are not implemented yet.')).toBeInTheDocument()
  })

  it('formats token cost and token count for today', () => {
    render(<StatsGrid snapshot={riskSnapshot} />)

    expect(screen.getByText('EUR 12.34')).toBeInTheDocument()
    expect(screen.getByText('45,678 token(s) recorded today.')).toBeInTheDocument()
  })
})
