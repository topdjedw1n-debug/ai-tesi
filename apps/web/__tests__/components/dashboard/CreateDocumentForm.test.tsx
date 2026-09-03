/**
 * Tests for CreateDocumentForm in Stage 0 "sales disabled" mode.
 *
 * With the user payment flow off, the form must not fetch or show pricing,
 * must not enter the payment step, and must route straight to the document
 * detail page after creating the draft. Generation may start only after the
 * manager reviews and confirms the task contract there.
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
    delete: jest.fn(),
  },
  getAccessToken: jest.fn(() => 'test-token'),
  API_ENDPOINTS: {
    DOCUMENTS: {
      CREATE: '/api/v1/documents/',
      UPLOAD_REQUIREMENTS: (id: number) =>
        `/api/v1/documents/${id}/custom-requirements/upload`,
      DELETE: (id: number) => `/api/v1/documents/${id}`,
    },
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
      screen.getByRole('button', { name: /створити чернетку/i })
    ).toBeInTheDocument()
  })

  it('creates without a methodology, does not start generation, and routes to review', async () => {
    render(<CreateDocumentForm />)

    fireEvent.change(screen.getByTestId('document-topic-input'), {
      target: { value: 'The impact of artificial intelligence on education systems' },
    })
    fireEvent.change(screen.getByTestId('document-deadline-input'), {
      target: { value: '2026-07-15' },
    })
    fireEvent.change(screen.getByTestId('document-requirements-input'), {
      target: { value: 'Use the university methodology template.' },
    })
    fireEvent.submit(screen.getByTestId('create-document-form'))

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/documents/',
        expect.objectContaining({
          target_pages: 45,
          citation_style: 'apa',
          work_type: 'tesi_magistrale',
          additional_requirements: expect.stringContaining('Deadline: 2026-07-15'),
        }),
        expect.any(Object)
      )
    })
    const payload = (apiClient.post as jest.Mock).mock.calls[0][1]
    expect(payload.title).toContain('artificial intelligence')
    expect(payload.additional_requirements).not.toContain('Тип роботи:')
    expect(payload.additional_requirements).toContain('Citation style: APA')
    expect(payload.additional_requirements).toContain('Use the university methodology template.')

    expect(apiClient.post).not.toHaveBeenCalledWith(
      '/api/v1/generate/full-document',
      expect.anything(),
      expect.anything()
    )
    expect(mockRouter.push).toHaveBeenCalledWith('/dashboard/documents/123')
    // Never enters the payment step.
    expect(screen.queryByText(/потрібна оплата/i)).not.toBeInTheDocument()
  })

  it('uploads an optional methodology before routing, without starting generation', async () => {
    render(<CreateDocumentForm />)

    fireEvent.change(screen.getByTestId('document-topic-input'), {
      target: { value: 'Corporate governance in Italian family businesses' },
    })
    const methodology = new File(['university rules'], 'linee-guida.pdf', {
      type: 'application/pdf',
    })
    fireEvent.change(screen.getByTestId('document-methodology-input'), {
      target: { files: [methodology] },
    })
    fireEvent.submit(screen.getByTestId('create-document-form'))

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/documents/123/custom-requirements/upload',
        expect.any(FormData),
        expect.any(Object)
      )
    })

    const calls = (apiClient.post as jest.Mock).mock.calls
    const uploadIndex = calls.findIndex(
      ([url]) => url === '/api/v1/documents/123/custom-requirements/upload'
    )
    expect(uploadIndex).toBeGreaterThan(-1)
    expect(calls.some(([url]) => url === '/api/v1/generate/full-document')).toBe(false)
    expect(mockRouter.push).toHaveBeenCalledWith('/dashboard/documents/123')
  })

  it('maps the selected UI work type to the backend contract field', async () => {
    render(<CreateDocumentForm />)

    fireEvent.change(screen.getByTestId('document-topic-input'), {
      target: { value: 'Digital governance in Italian public universities' },
    })
    fireEvent.change(screen.getByTestId('document-workType-input'), {
      target: { value: 'tesi_triennale' },
    })
    fireEvent.submit(screen.getByTestId('create-document-form'))

    await waitFor(() => {
      expect(apiClient.post).toHaveBeenCalledWith(
        '/api/v1/documents/',
        expect.objectContaining({ work_type: 'tesi_triennale' }),
        expect.any(Object)
      )
    })
  })

  it('shows a validation error when the topic is missing', async () => {
    render(<CreateDocumentForm />)
    fireEvent.submit(screen.getByTestId('create-document-form'))
    await waitFor(() => {
      expect(screen.getByText('Обов’язкове поле')).toBeInTheDocument()
    })
    expect(apiClient.post).not.toHaveBeenCalled()
  })
})
