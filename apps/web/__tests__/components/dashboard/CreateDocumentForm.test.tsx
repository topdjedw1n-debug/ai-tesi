/**
 * Tests for CreateDocumentForm in Stage 0 "sales disabled" mode.
 *
 * With the user payment flow off, the form must not fetch or show pricing,
 * must not enter the payment step, and must route straight to the document
 * detail page after creating the draft (kicking generation off on the way).
 *
 * The form is config-driven: fields come from lib/intake-fields.ts and
 * non-core fields are serialized into additional_requirements.
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
    GENERATE: { FULL: '/api/v1/generate/full-document' },
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
      screen.queryByRole('button', { name: /оплат/i })
    ).not.toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /згенерувати роботу/i })
    ).toBeInTheDocument()
  })

  it('creates the draft, starts generation and routes to the document page', async () => {
    render(<CreateDocumentForm />)

    fireEvent.change(screen.getByTestId('document-topic-input'), {
      target: { value: 'The impact of artificial intelligence on education systems' },
    })
    fireEvent.change(screen.getByTestId('document-deadline-input'), {
      target: { value: '2026-07-15' },
    })
    fireEvent.change(screen.getByTestId('document-citationStyle-input'), {
      target: { value: 'Chicago' },
    })
    fireEvent.change(screen.getByTestId('document-requirements-input'), {
      target: { value: 'Use the university methodology template.' },
    })
    fireEvent.click(screen.getByTestId('create-document-submit'))

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/documents',
        expect.objectContaining({
          target_pages: 45,
          additional_requirements: expect.stringContaining('Deadline: 2026-07-15'),
        }),
        expect.any(Object)
      )
    })
    const payload = (apiClient.post as jest.Mock).mock.calls[0][1]
    expect(payload.title).toContain('artificial intelligence')
    expect(payload.additional_requirements).toContain('Citation style: Chicago')
    expect(payload.additional_requirements).toContain('Use the university methodology template.')

    // Free MVP mode: generation is kicked off right after the draft.
    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/generate/full-document',
        { document_id: 123 },
        expect.any(Object)
      )
    })
    expect(mockRouter.push).toHaveBeenCalledWith('/dashboard/documents/123')
    // Never enters the payment step.
    expect(screen.queryByText(/потрібна оплата/i)).not.toBeInTheDocument()
  })

  it('shows a validation error when the topic is missing', async () => {
    render(<CreateDocumentForm />)
    fireEvent.click(screen.getByTestId('create-document-submit'))
    await waitFor(() => {
      expect(screen.getByText('Обов’язкове поле')).toBeInTheDocument()
    })
    expect(apiClient.post).not.toHaveBeenCalled()
  })
})
