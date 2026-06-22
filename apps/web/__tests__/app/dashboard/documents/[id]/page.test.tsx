/**
 * Tests for the document detail page "Start generation" action (Stage 0).
 *
 * A draft document shows a Start generation button that POSTs to the
 * full-document endpoint. Backend guardrails (402/400/429) surface their
 * human-readable detail via a toast and leave the document untouched.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useParams, useRouter } from 'next/navigation'
import DocumentDetailPage from '@/app/dashboard/documents/[id]/page'
import { apiClient } from '@/lib/api'
import toast from 'react-hot-toast'

jest.mock('next/navigation', () => ({
  useParams: jest.fn(),
  useRouter: jest.fn(),
}))

jest.mock('@/lib/api', () => ({
  apiClient: { get: jest.fn(), post: jest.fn() },
  getAccessToken: jest.fn(() => 'test-token'),
  API_ENDPOINTS: {
    DOCUMENTS: {
      GET: (id: number) => `/api/v1/documents/${id}`,
      PROVENANCE: (id: number) => `/api/v1/documents/${id}/provenance`,
    },
    GENERATE: { FULL: '/api/v1/generate/full-document' },
  },
}))

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}))

jest.mock('@/components/layout/DashboardLayout', () => ({
  DashboardLayout: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}))
jest.mock('@/components/GenerationProgress', () => ({
  GenerationProgress: () => <div data-testid="generation-progress" />,
}))
jest.mock('@/components/dashboard/DocumentSources', () => ({
  DocumentSources: () => <div data-testid="document-sources" />,
}))
jest.mock('@/components/dashboard/DocumentQualityEvidence', () => ({
  DocumentQualityEvidence: () => <div data-testid="document-quality-evidence" />,
}))

const draftDocument = {
  id: 123,
  title: 'Test Thesis',
  topic: 'AI in education',
  status: 'draft',
  content: null,
  outline: null,
  word_count: 0,
  created_at: '2026-06-22T00:00:00Z',
  updated_at: '2026-06-22T00:00:00Z',
  sections: [],
}

const completedDocument = {
  ...draftDocument,
  status: 'completed',
  content: 'Generated thesis content',
  word_count: 1200,
}

describe('DocumentDetailPage — Start generation (Stage 0)', () => {
  const mockRouter = { push: jest.fn(), refresh: jest.fn() }

  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue(mockRouter)
    ;(useParams as jest.Mock).mockReturnValue({ id: '123' })
    ;(apiClient.get as jest.Mock).mockResolvedValue(draftDocument)
  })

  it('renders the Start generation button on a draft document', async () => {
    render(<DocumentDetailPage />)
    await waitFor(() => {
      expect(screen.getByTestId('start-generation-button')).toBeInTheDocument()
    })
  })

  it('POSTs to the full-document endpoint when clicked', async () => {
    ;(apiClient.post as jest.Mock).mockResolvedValue({ job_id: 1, status: 'queued' })
    render(<DocumentDetailPage />)

    const button = await screen.findByTestId('start-generation-button')
    fireEvent.click(button)

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/generate/full-document',
        { document_id: 123 }
      )
    })
    expect(toast.success).toHaveBeenCalled()
  })

  it('surfaces the backend detail and keeps the draft on a 429', async () => {
    ;(apiClient.post as jest.Mock).mockRejectedValue(
      new Error('Daily free-generation limit reached (2 per day).')
    )
    render(<DocumentDetailPage />)

    const button = await screen.findByTestId('start-generation-button')
    fireEvent.click(button)

    await waitFor(() => {
      expect(toast.error).toHaveBeenCalledWith(
        'Daily free-generation limit reached (2 per day).'
      )
    })
    // Button is re-enabled and the draft is still shown.
    expect(screen.getByTestId('start-generation-button')).not.toBeDisabled()
  })

  it('renders Phase 1 QA evidence on completed documents', async () => {
    ;(apiClient.get as jest.Mock).mockResolvedValue(completedDocument)

    render(<DocumentDetailPage />)

    expect(await screen.findByTestId('document-quality-evidence')).toBeInTheDocument()
    expect(screen.getByTestId('document-sources')).toBeInTheDocument()
  })
})
