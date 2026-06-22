/**
 * Tests for CreateDocumentForm in Stage 0 "sales disabled" mode.
 *
 * With the user payment flow off, the form must not fetch or show pricing,
 * must not enter the payment step, and must route straight to the document
 * detail page after creating the draft.
 */
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import { useRouter } from 'next/navigation'
import { CreateDocumentForm } from '@/components/dashboard/CreateDocumentForm'
import { apiClient } from '@/lib/api'

// Sales disabled (Stage 0 MVP default).
jest.mock('@/lib/feature-flags', () => ({
  isUserPaymentFlowEnabled: false,
}))

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}))

jest.mock('@/lib/api', () => ({
  apiClient: {
    get: jest.fn(),
    post: jest.fn(),
  },
  getAccessToken: jest.fn(() => 'test-token'),
  API_ENDPOINTS: {
    DOCUMENTS: { CREATE: '/api/v1/documents' },
    PRICING: { CURRENT: '/api/v1/pricing/current' },
  },
}))

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}))

describe('CreateDocumentForm — sales disabled (Stage 0)', () => {
  const mockRouter = { push: jest.fn(), refresh: jest.fn() }

  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue(mockRouter)
    ;(apiClient.post as jest.Mock).mockResolvedValue({ id: 123 })
  })

  it('does not fetch pricing on mount', async () => {
    render(<CreateDocumentForm />)
    // Give effects a tick to run.
    await waitFor(() => {
      expect(screen.getByTestId('create-document-form')).toBeInTheDocument()
    })
    expect(apiClient.get).not.toHaveBeenCalled()
  })

  it('does not render the price preview or a payment CTA', () => {
    render(<CreateDocumentForm />)
    expect(screen.queryByText(/estimated cost/i)).not.toBeInTheDocument()
    expect(
      screen.queryByRole('button', { name: /continue to payment/i })
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /^create document$/i })
    ).toBeInTheDocument()
  })

  it('creates the draft and routes to the document page without a payment step', async () => {
    render(<CreateDocumentForm />)

    fireEvent.change(screen.getByTestId('document-title-input'), {
      target: { value: 'My Thesis' },
    })
    fireEvent.change(screen.getByTestId('document-topic-input'), {
      target: { value: 'The impact of artificial intelligence on education systems' },
    })
    fireEvent.change(screen.getByTestId('document-deadline-input'), {
      target: { value: '2026-07-15' },
    })
    fireEvent.change(screen.getByTestId('document-citation-style-select'), {
      target: { value: 'Chicago' },
    })
    fireEvent.change(screen.getByTestId('document-additional-requirements-input'), {
      target: { value: 'Use the university methodology template.' },
    })
    fireEvent.click(screen.getByTestId('create-document-submit'))

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/documents',
        expect.objectContaining({
          target_pages: 10,
          additional_requirements: expect.stringContaining('Deadline: 2026-07-15'),
        }),
        expect.any(Object)
      )
    })
    const payload = (apiClient.post as jest.Mock).mock.calls[0][1]
    expect(payload.additional_requirements).toContain('Citation style: Chicago')
    expect(payload.additional_requirements).toContain('Use the university methodology template.')
    expect(mockRouter.push).toHaveBeenCalledWith('/dashboard/documents/123')
    // Never enters the payment step.
    expect(screen.queryByText(/payment required/i)).not.toBeInTheDocument()
  })
})
