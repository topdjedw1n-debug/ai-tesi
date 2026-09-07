import { apiClient, API_ENDPOINTS } from '../api'

// Regression: ISSUE-001 — invalid credentials reloaded and cleared the login form.
// Found by /qa on 2026-09-07.
// Report: .gstack/qa-reports/qa-report-localhost-2026-09-07.md
describe('login errors without session recovery', () => {
  const originalFetch = global.fetch

  afterEach(() => {
    global.fetch = originalFetch
    localStorage.clear()
  })

  it('returns the login error without redirecting or attempting token refresh', async () => {
    const fetchSpy = jest.fn().mockResolvedValue({
      ok: false, status: 401, json: async () => ({ detail: 'Invalid credentials' }),
    } as Response)
    global.fetch = fetchSpy

    await expect(apiClient.post(API_ENDPOINTS.AUTH.LOGIN, {
      username: 'qa-manager', password: 'incorrect',
    })).rejects.toThrow('Invalid credentials')

    expect(fetchSpy).toHaveBeenCalledTimes(1)
    expect(fetchSpy.mock.calls[0][0]).toContain(API_ENDPOINTS.AUTH.LOGIN)
  })
})
