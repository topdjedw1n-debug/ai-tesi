import { act, render, screen, waitFor } from '@testing-library/react'
import { GenerationProgress } from '@/components/GenerationProgress'
import { useWebSocket } from '@/hooks/useWebSocket'
import { apiClient } from '@/lib/api'

jest.mock('@/lib/api', () => ({
  apiClient: { get: jest.fn() },
  API_ENDPOINTS: { JOBS: { FOR_DOCUMENT: (id: number) => `/api/v1/jobs/document/${id}/status` } },
}))

jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: jest.fn(),
}))

describe('GenerationProgress', () => {
  let onMessage: (message: Record<string, unknown>) => void

  beforeEach(() => {
    jest.clearAllMocks()
    ;(apiClient.get as jest.Mock).mockResolvedValue(null)
    ;(useWebSocket as jest.Mock).mockImplementation((options) => {
      onMessage = options.onMessage
      return {
        isConnected: true,
        isConnecting: false,
        error: null,
        lastMessage: null,
        reconnectAttempts: 0,
        connect: jest.fn(),
        disconnect: jest.fn(),
      }
    })
  })

  it('shows a retry as a non-terminal state and preserves progress', async () => {
    const onError = jest.fn()
    render(<GenerationProgress documentId={123} onError={onError} />)
    await act(async () => {})

    act(() => {
      onMessage({
        type: 'progress_update',
        progress_percentage: 37,
        current_section: 'Методологія',
      })
    })
    expect(screen.getByText('37%')).toBeInTheDocument()

    act(() => {
      onMessage({
        type: 'job_retrying',
        status: 'queued',
        error: 'Temporary provider outage',
      })
    })

    expect(screen.getByText('Повторна спроба')).toBeInTheDocument()
    expect(screen.getByText('37%')).toBeInTheDocument()
    expect(screen.queryByText('Помилка генерації')).not.toBeInTheDocument()
    expect(onError).not.toHaveBeenCalled()
  })

  it('restores the saved progress after reload without a websocket event', async () => {
    ;(apiClient.get as jest.Mock).mockResolvedValue({ document_id: 123, job_id: 7, status: 'queued', progress: 47, attempt_count: 1 })
    render(<GenerationProgress documentId={123} />)
    expect(await screen.findByText('47%')).toBeInTheDocument()
    expect(screen.getByText('Повторна спроба')).toBeInTheDocument()
    expect(screen.getByText(/Завершені розділи зберігаються/)).toBeInTheDocument()
  })

  it.each([true, false])('merges a delayed poll with socket detail (connected=%s)', async (connected) => {
    let resolvePoll: (value: unknown) => void = () => {}
    ;(apiClient.get as jest.Mock).mockReturnValue(new Promise((resolve) => { resolvePoll = resolve }))
    ;(useWebSocket as jest.Mock).mockImplementation((options) => {
      onMessage = options.onMessage
      return { isConnected: connected, isConnecting: false, error: null }
    })
    render(<GenerationProgress documentId={123} />)
    act(() => onMessage({
      type: 'progress_update', document_id: 123, progress_percentage: 73,
      current_section: 'Методологія', estimated_time: '2 хв',
    }))
    await act(async () => resolvePoll({
      document_id: 123, job_id: 7, status: 'running', progress: 47, attempt_count: 1,
    }))
    expect(screen.getByText(connected ? '73%' : '47%')).toBeInTheDocument()
    expect(screen.getByText('Методологія')).toBeInTheDocument()
    expect(screen.getByText(/2 хв/)).toBeInTheDocument()
  })

  it('does not reopen a completed job when an older poll returns late', async () => {
    let resolvePoll: (value: unknown) => void = () => {}
    ;(apiClient.get as jest.Mock).mockReturnValue(new Promise((resolve) => { resolvePoll = resolve }))
    const onComplete = jest.fn()
    render(<GenerationProgress documentId={123} onComplete={onComplete} />)
    act(() => onMessage({ type: 'job_completed', document_id: 123 }))
    await act(async () => resolvePoll({ document_id: 123, status: 'running', progress: 47 }))
    expect(screen.getByText('Написання завершено')).toBeInTheDocument()
    expect(screen.getByText('100%')).toBeInTheDocument()
    expect(onComplete).toHaveBeenCalledTimes(1)
  })

  it('keeps socket loss separate from generation failure and ignores other work', async () => {
    const onError = jest.fn()
    ;(useWebSocket as jest.Mock).mockImplementation((options) => {
      onMessage = options.onMessage
      return { isConnected: false, isConnecting: false, error: 'Connection lost' }
    })
    ;(apiClient.get as jest.Mock).mockResolvedValue({ document_id: 123, status: 'running', progress: 47 })
    render(<GenerationProgress documentId={123} onError={onError} />)
    await screen.findByText('47%')
    act(() => onMessage({ type: 'job_failed', document_id: 124, error: 'Foreign failure' }))
    expect(screen.getByText('47%')).toBeInTheDocument()
    expect(screen.getByText(/це не означає зупинку генерації/)).toBeInTheDocument()
    expect(screen.queryByText('Помилка генерації')).not.toBeInTheDocument()
    expect(onError).not.toHaveBeenCalled()
  })

  it('restores a terminal reason once and explains what must be fixed', async () => {
    const onError = jest.fn()
    ;(apiClient.get as jest.Mock).mockResolvedValue({ document_id: 123, status: 'failed', progress: 12, error_message: 'Too few citable sources' })
    render(<GenerationProgress documentId={123} active={false} onError={onError} />)
    expect(await screen.findByText('Too few citable sources')).toBeInTheDocument()
    expect(screen.getByText(/PDF/)).toBeInTheDocument()
    act(() => onMessage({ type: 'job_failed', document_id: 123, error: 'Too few citable sources' }))
    await waitFor(() => expect(onError).toHaveBeenCalledTimes(1))
  })
})
