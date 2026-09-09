import { act, render, screen } from '@testing-library/react'
import { GenerationProgress } from '@/components/GenerationProgress'
import { apiClient } from '@/lib/api'
import { useWebSocket } from '@/hooks/useWebSocket'
jest.mock('@/hooks/useWebSocket', () => ({ useWebSocket: jest.fn() }))
jest.mock('@/lib/api', () => ({ apiClient: { get: jest.fn() }, API_ENDPOINTS: { JOBS: { FOR_DOCUMENT: (id: number) => `/jobs/document/${id}/status` } } }))
const base = { executor_version: 2, job_id: 12, status: 'running', status_label: 'Виконується', progress: 55, stage_label: 'Написання розділів', sections_done: 2, sections_total: 6, last_signal: 'Розділ збережено.', warnings_count: 3, tokens_so_far: 2500, cost_cents_so_far: 14, heartbeat_at: '2026-09-09T12:00:00Z', observed_at: '2026-09-09T12:00:10Z' }
beforeEach(() => jest.clearAllMocks())
it('restores API labels, sections, cost and warnings by GET without a socket', async () => {
  ;(apiClient.get as jest.Mock).mockResolvedValue(base)
  render(<GenerationProgress documentId={11} active={false} />)
  expect(await screen.findByText('Написання розділів')).toBeInTheDocument()
  expect(screen.getByText('Розділів збережено: 2 із 6')).toBeInTheDocument()
  expect(screen.getByText(/\$0.14 · 3 попереджень/)).toBeInTheDocument()
  expect(screen.getByRole('progressbar')).toHaveAttribute('aria-valuenow', '55')
  expect(useWebSocket).not.toHaveBeenCalled()
})
it.each([true, false])('uses five minute heartbeat threshold (stale=%s)', async stale => {
  ;(apiClient.get as jest.Mock).mockResolvedValue({ ...base, observed_at: stale ? '2026-09-09T12:05:01Z' : '2026-09-09T12:05:00Z' })
  render(<GenerationProgress documentId={11} active={false} />)
  await screen.findByText('Написання розділів')
  expect(!!screen.queryByText('Виконавець не відповідає.')).toBe(stale)
  if (stale) expect(screen.getByRole('button', { name: 'Звернутися до власника' })).toBeInTheDocument()
})
it('shows the API technical stop and one owner action', async () => {
  const stop = { code: 'provider_access', message_uk: 'Потрібно поповнити баланс моделі.', next_action: 'retry_after_owner', next_action_label: 'Звернутися до власника', retryable: false }
  ;(apiClient.get as jest.Mock).mockResolvedValue({ ...base, status: 'failed', status_label: 'Технічна зупинка', stop })
  const onError = jest.fn()
  render(<GenerationProgress documentId={11} active={false} onError={onError} />)
  expect(await screen.findByText(stop.message_uk)).toBeInTheDocument()
  expect(screen.getAllByRole('button')).toHaveLength(1)
  expect(screen.queryByRole('progressbar')).not.toBeInTheDocument()
  expect(onError).toHaveBeenCalledWith(stop.message_uk)
})
it('retains saved progress after a polling failure', async () => {
  jest.useFakeTimers()
  ;(apiClient.get as jest.Mock).mockResolvedValueOnce(base).mockRejectedValue(new Error('offline'))
  render(<GenerationProgress documentId={11} />)
  await act(async () => {})
  await act(async () => { jest.advanceTimersByTime(3000) })
  expect(screen.getByText(/Не вдалося оновити стан/)).toBeInTheDocument()
  expect(screen.getByText('Розділ збережено.')).toBeInTheDocument()
  jest.useRealTimers()
})
it('renders cancellation without a technical stop', async () => {
  ;(apiClient.get as jest.Mock).mockResolvedValue({ ...base, status: 'cancelled', status_label: 'Скасовано', stop: null })
  const onError = jest.fn(), onCancelled = jest.fn()
  render(<GenerationProgress documentId={11} active={false} onError={onError} onCancelled={onCancelled} />)
  expect(await screen.findByText('Скасовано')).toBeInTheDocument()
  expect(screen.queryByRole('button')).not.toBeInTheDocument()
  expect(onError).not.toHaveBeenCalled()
  expect(onCancelled).toHaveBeenCalledTimes(1)
})

it('ages the last heartbeat while the status API is unavailable', async () => {
  jest.useFakeTimers()
  ;(apiClient.get as jest.Mock).mockResolvedValueOnce(base).mockRejectedValue(new Error('DB unavailable'))
  render(<GenerationProgress documentId={11} />)
  await act(async () => {})
  await act(async () => { jest.advanceTimersByTime(310000) })
  expect(screen.getByText('Виконавець не відповідає.')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Звернутися до власника' })).toBeInTheDocument()
  jest.useRealTimers()
})
