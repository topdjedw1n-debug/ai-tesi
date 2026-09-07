import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { TaskContractPanel } from '@/components/dashboard/TaskContractPanel'
import { apiClient } from '@/lib/api'

jest.mock('@/lib/api', () => ({
  apiClient: { get: jest.fn(), post: jest.fn() },
  API_ENDPOINTS: {
    DOCUMENTS: {
      TASK_CONTRACT: (id: number) => `/api/v1/documents/${id}/task-contract`,
      CONFIRM_TASK_CONTRACT: (id: number) =>
        `/api/v1/documents/${id}/task-contract/confirm`,
    },
    GENERATE: {
      FULL: '/api/v1/generate/full-document',
      ESTIMATE_COST: ({
        provider,
        model,
        targetPages,
      }: {
        provider: string
        model: string
        targetPages: number
      }) =>
        `/api/v1/generate/estimate-cost?provider=${provider}&model=${model}&target_pages=${targetPages}`,
    },
  },
}))

jest.mock('react-hot-toast', () => ({
  __esModule: true,
  default: { error: jest.fn(), success: jest.fn() },
}))

const contract = {
  version: 1,
  document_id: 123,
  basis: 'standard_academic',
  basis_label: 'standard academic rules with manager-confirmed parameters',
  rules: [
    {
      key: 'topic',
      value: 'AI in Italian education',
      source: 'intake',
      status: 'explicit',
    },
    {
      key: 'work_type',
      value: 'tesi_magistrale',
      source: 'intake',
      status: 'explicit',
    },
    {
      key: 'language',
      value: 'it',
      source: 'intake',
      status: 'explicit',
    },
    {
      key: 'citation_style',
      value: 'apa',
      source: 'intake',
      status: 'explicit',
    },
    {
      key: 'structure',
      value: 'introduction; chapters; conclusions',
      source: 'system_default',
      status: 'assumed',
    },
  ],
  assumptions: [
    {
      key: 'structure',
      value: 'introduction; chapters; conclusions',
      source: 'system_default',
      status: 'assumed',
    },
  ],
  confirmation_required: true,
  sha256: 'a'.repeat(64),
  confirmed: false,
  confirmed_at: null,
}

describe('TaskContractPanel', () => {
  beforeEach(() => {
    jest.clearAllMocks()
    ;(apiClient.get as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/task-contract')) return Promise.resolve(contract)
      return Promise.resolve({
        estimated_cost_usd: 12.3456,
        estimated_total_tokens: 85000,
        currency: 'USD',
      })
    })
    ;(apiClient.post as jest.Mock).mockResolvedValue({ confirmed: true })
  })

  it('requires resolution of the failed attempt before an explicit new paid start', async () => {
    render(<TaskContractPanel documentId={123} targetPages={18} provider="anthropic" model="claude-opus-4-8" retry />)
    const start = await screen.findByRole('button', { name: 'Підтвердити нову спробу' })
    fireEvent.click(screen.getByTestId('task-contract-confirmation'))
    expect(start).toBeDisabled()
    expect(apiClient.post).not.toHaveBeenCalled()
    fireEvent.click(screen.getByLabelText(/Причину попередньої зупинки з’ясовано/))
    fireEvent.click(start)
    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(2))
  })

  it('shows explicit and assumed rules plus the estimate', async () => {
    render(
      <TaskContractPanel
        documentId={123}
        targetPages={45}
        provider="anthropic"
        model="claude-opus-4-8"
      >
        <div>Source files slot</div>
      </TaskContractPanel>
    )

    expect(await screen.findByText('Контракт роботи')).toBeInTheDocument()
    expect(screen.getAllByText('Явно задано')).toHaveLength(4)
    expect(screen.getByText('Припущення')).toBeInTheDocument()
    expect(screen.getByText('Магістерська')).toBeInTheDocument()
    expect(screen.getByText('Італійська')).toBeInTheDocument()
    expect(screen.getByText('APA')).toBeInTheDocument()
    expect(screen.getByText('$12.35')).toBeInTheDocument()
    expect(screen.getByText('Source files slot')).toBeInTheDocument()
    expect(screen.getByTestId('confirm-and-start-button')).toBeDisabled()
  })

  it('confirms first and starts generation second after the manager checks the box', async () => {
    const onGenerationStarted = jest.fn()
    render(
      <TaskContractPanel
        documentId={123}
        targetPages={45}
        provider="anthropic"
        model="claude-opus-4-8"
        onGenerationStarted={onGenerationStarted}
      />
    )

    await screen.findByText('Контракт роботи')
    fireEvent.click(screen.getByTestId('task-contract-confirmation'))
    const startButton = screen.getByTestId('confirm-and-start-button')
    expect(startButton).toBeEnabled()
    fireEvent.click(startButton)

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(2))
    expect((apiClient.post as jest.Mock).mock.calls.map(([url]) => url)).toEqual([
      '/api/v1/documents/123/task-contract/confirm',
      '/api/v1/generate/full-document',
    ])
    expect(apiClient.post).toHaveBeenNthCalledWith(
      2,
      '/api/v1/generate/full-document',
      { document_id: 123 }
    )
    expect(onGenerationStarted).toHaveBeenCalledTimes(1)
  })

  it('does not duplicate confirmation when the current contract is already confirmed', async () => {
    ;(apiClient.get as jest.Mock).mockImplementation((url: string) => {
      if (url.includes('/task-contract')) {
        return Promise.resolve({ ...contract, confirmed: true })
      }
      return Promise.resolve({ estimated_cost_usd: 12, estimated_total_tokens: 85000 })
    })

    render(
      <TaskContractPanel
        documentId={123}
        targetPages={45}
        provider="anthropic"
        model="claude-opus-4-8"
      />
    )

    await screen.findByText(/вже було підтверджено/i)
    fireEvent.click(screen.getByTestId('task-contract-confirmation'))
    fireEvent.click(screen.getByTestId('confirm-and-start-button'))

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1))
    expect(apiClient.post).toHaveBeenCalledWith(
      '/api/v1/generate/full-document',
      { document_id: 123 }
    )
  })
})
