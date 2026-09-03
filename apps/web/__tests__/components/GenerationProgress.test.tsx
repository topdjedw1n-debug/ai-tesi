import { act, render, screen } from '@testing-library/react'
import { GenerationProgress } from '@/components/GenerationProgress'
import { useWebSocket } from '@/hooks/useWebSocket'

jest.mock('@/hooks/useWebSocket', () => ({
  useWebSocket: jest.fn(),
}))

describe('GenerationProgress', () => {
  let onMessage: (message: Record<string, unknown>) => void

  beforeEach(() => {
    jest.clearAllMocks()
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

  it('shows a retry as a non-terminal state and preserves progress', () => {
    const onError = jest.fn()
    render(<GenerationProgress documentId={123} onError={onError} />)

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
})
