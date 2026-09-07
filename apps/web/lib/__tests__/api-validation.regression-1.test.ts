import { apiClient } from '../api'

// ISSUE-006: structured FastAPI validation errors were shown as [object Object].
// Found by /qa on 2026-09-07.
// Report: .gstack/qa-reports/qa-report-localhost-2026-09-07.md
describe('readable API validation failures', () => {
  const originalFetch = global.fetch
  afterEach(() => { global.fetch = originalFetch; localStorage.clear() })

  it.each([
    [[{ loc: ['body', 'topic'], msg: 'Too short' }, { loc: ['body', 'topic'] }], 'Перевір введені дані (тема) та спробуй ще раз.'],
    [[{ loc: ['body', 'unknown'] }, null], 'Перевір введені дані у формі та спробуй ще раз.'],
  ])('shows usable guidance without serializing validation objects', async (detail, expected) => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false, status: 422, json: async () => ({ detail }),
    } as Response)
    await expect(apiClient.post('/api/v1/documents/', {})).rejects.toThrow(expected)
  })

  it('preserves the server explanation for ordinary business rule errors', async () => {
    global.fetch = jest.fn().mockResolvedValue({
      ok: false, status: 409, json: async () => ({ detail: 'No active generation job to cancel' }),
    } as Response)
    await expect(apiClient.post('/api/v1/generate/full-document/1/cancel', {}))
      .rejects.toThrow('No active generation job to cancel')
  })
})
