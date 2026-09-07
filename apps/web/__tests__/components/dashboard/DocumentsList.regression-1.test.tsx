import { fireEvent, render, screen, waitFor } from '@testing-library/react'
import { DocumentsList } from '@/components/dashboard/DocumentsList'
import { apiClient } from '@/lib/api'

jest.mock('@/lib/api', () => ({
  apiClient: { get: jest.fn() },
  API_ENDPOINTS: { DOCUMENTS: { LIST: '/api/v1/documents/' } },
}))

// Regression: ISSUE-004 — request failure was shown as an empty account.
// Found by /qa on 2026-09-07.
// Report: .gstack/qa-reports/qa-report-localhost-2026-09-07.md
it('offers recovery from a failed list request without reporting an empty account', async () => {
  const consoleSpy = jest.spyOn(console, 'error').mockImplementation(() => {})
  ;(apiClient.get as jest.Mock)
    .mockRejectedValueOnce(new TypeError('Failed to fetch'))
    .mockResolvedValueOnce({ documents: [{
      id: 15, title: 'Saved academic work', topic: 'Nursing', status: 'draft',
      created_at: '2026-09-07T10:00:00Z', word_count: 0,
    }] })
  try {
    render(<DocumentsList />)
    expect(await screen.findByRole('alert')).toHaveTextContent('Не вдалося завантажити роботи')
    expect(screen.queryByTestId('empty-documents-message')).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: 'Спробувати ще раз' }))
    expect(await screen.findByText('Saved academic work')).toBeInTheDocument()
    await waitFor(() => expect(screen.queryByRole('alert')).not.toBeInTheDocument())
    expect(apiClient.get).toHaveBeenCalledTimes(2)
  } finally {
    consoleSpy.mockRestore()
  }
})

// ISSUE-009: a failed job's document word count can still describe the brief.
it('does not show the brief word count as the size of failed work', async () => {
  ;(apiClient.get as jest.Mock).mockResolvedValue({ documents: [{
    id: 5, title: 'Interrupted nursing review', topic: 'Nursing', status: 'failed',
    created_at: '2026-09-07T10:00:00Z', word_count: 22,
  }] })
  render(<DocumentsList />)
  expect(await screen.findByText('Interrupted nursing review')).toBeInTheDocument()
  expect(screen.queryByText('22 слів')).not.toBeInTheDocument()
})
