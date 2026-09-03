import { useState } from 'react'
import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { useRouter } from 'next/navigation'
import { CreateDocumentForm } from '@/components/dashboard/CreateDocumentForm'
import { TaskContractPanel } from '@/components/dashboard/TaskContractPanel'
import { apiClient } from '@/lib/api'

jest.mock('next/navigation', () => ({
  useRouter: jest.fn(),
}))

jest.mock('@/lib/feature-flags', () => ({
  isUserPaymentFlowEnabled: false,
}))

jest.mock('@/lib/api', () => ({
  apiClient: {
    post: jest.fn(),
    get: jest.fn(),
    delete: jest.fn(),
  },
  getAccessToken: jest.fn(() => 'test-token'),
  API_ENDPOINTS: {
    DOCUMENTS: {
      CREATE: '/api/v1/documents/',
      DELETE: (id: number) => `/api/v1/documents/${id}`,
      UPLOAD_REQUIREMENTS: (id: number) =>
        `/api/v1/documents/${id}/custom-requirements/upload`,
      TASK_CONTRACT: (id: number) => `/api/v1/documents/${id}/task-contract`,
      CONFIRM_TASK_CONTRACT: (id: number) =>
        `/api/v1/documents/${id}/task-contract/confirm`,
    },
    GENERATE: {
      FULL: '/api/v1/generate/full-document',
      ESTIMATE_COST: () => '/api/v1/generate/estimate-cost',
    },
  },
}))

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}))

function CreationFlowHarness() {
  const [documentId, setDocumentId] = useState<number | null>(null)
  return documentId ? (
    <TaskContractPanel
      documentId={documentId}
      targetPages={45}
      provider="anthropic"
      model="claude-opus-4-8"
    />
  ) : (
    <CreateDocumentForm onSuccess={setDocumentId} />
  )
}

describe('Document creation and explicit start flow', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(useRouter as jest.Mock).mockReturnValue({ push: jest.fn(), refresh: jest.fn() })
    ;(apiClient.post as jest.Mock).mockImplementation((url: string) => {
      if (url === '/api/v1/documents/') return Promise.resolve({ id: 123 })
      return Promise.resolve({ confirmed: true })
    })
    ;(apiClient.get as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/task-contract')) {
        return Promise.resolve({
          version: 1,
          document_id: 123,
          basis: 'standard_academic',
          basis_label: 'standard academic rules',
          rules: [
            {
              key: 'work_type',
              value: 'tesi_magistrale',
              source: 'intake',
              status: 'explicit',
            },
            {
              key: 'structure',
              value: 'standard structure',
              source: 'system_default',
              status: 'assumed',
            },
          ],
          assumptions: [
            {
              key: 'structure',
              value: 'standard structure',
              source: 'system_default',
              status: 'assumed',
            },
          ],
          confirmation_required: true,
          sha256: 'a'.repeat(64),
          confirmed: false,
          confirmed_at: null,
        })
      }
      return Promise.resolve({ estimated_cost_usd: 10, estimated_total_tokens: 80000 })
    })
  })

  it('creates a draft first, then confirms the contract before generation', async () => {
    render(<CreationFlowHarness />)

    fireEvent.change(screen.getByTestId('document-topic-input'), {
      target: { value: 'Artificial intelligence in Italian higher education' },
    })
    fireEvent.submit(screen.getByTestId('create-document-form'))

    expect(await screen.findByText('Контракт роботи')).toBeInTheDocument()
    expect(
      (apiClient.post as jest.Mock).mock.calls.some(
        ([url]) => url === '/api/v1/generate/full-document'
      )
    ).toBe(false)

    fireEvent.click(screen.getByTestId('task-contract-confirmation'))
    fireEvent.click(screen.getByTestId('confirm-and-start-button'))

    await waitFor(() => {
      expect((apiClient.post as jest.Mock).mock.calls.map(([url]) => url)).toEqual([
        '/api/v1/documents/',
        '/api/v1/documents/123/task-contract/confirm',
        '/api/v1/generate/full-document',
      ])
    })
  })
})
