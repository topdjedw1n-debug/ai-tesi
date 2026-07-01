import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useParams } from 'next/navigation'
import ProductionCaseDetailPage from '@/app/admin/production-cases/[id]/page'
import { adminApiClient } from '@/lib/api/admin'

jest.mock('next/navigation', () => ({
  useParams: jest.fn(),
}))

jest.mock('@/lib/api/admin', () => ({
  adminApiClient: {
    getProductionCase: jest.fn(),
    getReleaseGates: jest.fn(),
    recordDetectorResult: jest.fn(),
    releaseProductionCase: jest.fn(),
    overrideReleaseGate: jest.fn(),
  },
}))

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}))

const productionCase = {
  id: 77,
  document_id: 123,
  client_user_id: 5,
  manager_id: 1,
  editor_id: null,
  deadline_at: null,
  citation_style: 'apa',
  requirements_text: null,
  intake_status: 'ready',
  generation_status: 'completed',
  qa_status: 'needs_review',
  editorial_status: 'needs_review',
  payment_status: 'internal_mvp',
  delivery_status: 'pending',
  release_status: 'blocked',
  human_minutes_budget: 120,
  human_minutes_used: 30,
  cost_cents: 0,
  release_notes: null,
  released_at: null,
  created_at: '2026-06-22T00:00:00Z',
  updated_at: '2026-06-22T00:00:00Z',
  document: {
    id: 123,
    title: 'Italy thesis',
    topic: 'Italian bachelor thesis',
    status: 'completed',
    language: 'it',
    target_pages: 20,
  },
  client_email: 'client@example.com',
  manager_email: 'manager@example.com',
  editor_email: null,
}

const aiDetectorGate = {
  id: null,
  production_case_id: 77,
  gate_key: 'ai_detection_proxy',
  status: 'no_data',
  severity: 'blocker',
  blocking: true,
  source: 'manual_detector',
  summary: 'Record a structured external detector result before release.',
  evidence: null,
  override_allowed: false,
  override_reason: null,
  overridden_by_id: null,
  overridden_at: null,
  last_checked_at: null,
}

describe('ProductionCaseDetailPage QA evidence', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(useParams as jest.Mock).mockReturnValue({ id: '77' })
    ;(adminApiClient.getProductionCase as jest.Mock).mockResolvedValue(productionCase)
    ;(adminApiClient.getReleaseGates as jest.Mock).mockResolvedValue([aiDetectorGate])
    ;(adminApiClient.recordDetectorResult as jest.Mock).mockResolvedValue({
      ...aiDetectorGate,
      status: 'passed',
    })
  })

  it('shows consolidated QA evidence and records structured detector results', async () => {
    render(<ProductionCaseDetailPage />)

    expect(await screen.findByText('QA Evidence')).toBeInTheDocument()
    expect(screen.getByText('ai_detection_proxy')).toBeInTheDocument()

    fireEvent.change(screen.getByLabelText('Result %'), {
      target: { value: '24' },
    })
    fireEvent.change(screen.getByLabelText('Threshold %'), {
      target: { value: '35' },
    })
    fireEvent.change(screen.getByLabelText('Reason'), {
      target: { value: 'Phase 1 proof run detector evidence.' },
    })

    fireEvent.click(screen.getByRole('button', { name: 'Record detector result' }))

    await waitFor(() => {
      expect(adminApiClient.recordDetectorResult).toHaveBeenCalledWith(
        77,
        'ai_detection_proxy',
        expect.objectContaining({
          detector_name: 'GPTZero',
          result_percent: 24,
          threshold_percent: 35,
          report_ref: 'docs/phase1-runs/RUN-001.md',
          reason: 'Phase 1 proof run detector evidence.',
        })
      )
    })
  })
})
