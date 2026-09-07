import { render, screen, within } from '@testing-library/react'
import { DocumentQualityEvidence } from '@/components/dashboard/DocumentQualityEvidence'
import { apiClient } from '@/lib/api'
import { adminApiClient } from '@/lib/api/admin'

jest.mock('@/lib/api/admin', () => ({ adminApiClient: { getReleaseGates: jest.fn() } }))

jest.mock('@/lib/api', () => ({
  apiClient: { get: jest.fn() },
  API_ENDPOINTS: {
    DOCUMENTS: {
      PROVENANCE: (id: number) => `/api/v1/documents/${id}/provenance`,
    },
  },
}))

const provenanceEvent = (
  id: number,
  event_type: string,
  payload: Record<string, unknown>
) => ({
  id,
  stage: 'verification',
  event_type,
  payload,
  created_at: '2026-09-03T10:00:00Z',
})

describe('DocumentQualityEvidence source decisions', () => {
  beforeEach(() => jest.clearAllMocks())

  it('shows current Compilatio decisions and never treats an old low number as a pass', async () => {
    ;(apiClient.get as jest.Mock).mockResolvedValue({ events: [] })
    ;(adminApiClient.getReleaseGates as jest.Mock).mockResolvedValue([
      { gate_key: 'plagiarism_proxy', status: 'failed', evidence: { result_percent: 5, binding_status: 'stale' } },
      { gate_key: 'ai_detection_proxy', status: 'passed', evidence: { result_percent: 10 } },
    ])
    render(<DocumentQualityEvidence documentId={123} productionCaseId={77} />)
    const plagiarism = (await screen.findByText('Compilatio: збіги тексту')).closest('li')!
    expect(within(plagiarism).getByText('Потребує уваги')).toBeInTheDocument()
    expect(within(plagiarism).getByText(/5% у Compilatio/)).toBeInTheDocument()
    const ai = screen.getByText('Compilatio: показник AI').closest('li')!
    expect(within(ai).getByText('Пройдено')).toBeInTheDocument()
    expect(adminApiClient.getReleaseGates).toHaveBeenCalledWith(77)
  })

  it('explains an insufficient source stop and names the actual writer', async () => {
    ;(apiClient.get as jest.Mock).mockResolvedValue({
      document_id: 123,
      total: 2,
      events: [
        provenanceEvent(1, 'section_writer', {
          actual: 'anthropic/claude-opus-4-8',
          planned: 'anthropic/claude-opus-4-8',
        }),
        provenanceEvent(2, 'source_pack_insufficient', {
          status: 'failed',
          citable_sources: 3,
          minimum_required: 5,
          message: 'Too few relevant sources.',
        }),
      ],
    })

    render(<DocumentQualityEvidence documentId={123} />)

    expect(
      await screen.findByText(/Знайдено лише 3 релевантних джерел із потрібних 5/)
    ).toBeInTheDocument()
    expect(
      screen.getByText(/Згенеровано моделлю claude-opus-4-8 \(anthropic\)/)
    ).toBeInTheDocument()
  })

  it('renders a successful preflight verdict in manager language', async () => {
    ;(apiClient.get as jest.Mock).mockResolvedValue({
      document_id: 123,
      total: 1,
      events: [
        provenanceEvent(1, 'source_pack_preflight', {
          status: 'passed',
          verified: 18,
          final_size: 18,
          target: 24,
          min_required: 18,
        }),
      ],
    })

    render(<DocumentQualityEvidence documentId={123} />)

    expect(
      await screen.findByText(/Перед стартом перевірено 18 джерел; мінімум 18 виконано/)
    ).toBeInTheDocument()
  })
})
