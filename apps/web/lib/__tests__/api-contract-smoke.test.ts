import { API_ENDPOINTS, apiClient } from '../api'
import { adminApiClient } from '../api/admin'
import { refundsApiClient } from '../api/refunds'

jest.mock('../feature-flags', () => ({
  isUserRefundFlowEnabled: true,
}))

describe('API contract smoke checks', () => {
  afterEach(() => {
    jest.restoreAllMocks()
  })

  it('uses canonical generation endpoints from backend contract', () => {
    expect(API_ENDPOINTS.GENERATE.FULL).toBe('/api/v1/generate/full-document')
    expect(typeof API_ENDPOINTS.GENERATE.USAGE).toBe('function')
    expect(API_ENDPOINTS.GENERATE.USAGE(42)).toBe('/api/v1/generate/usage/42')
  })

  it('does not expose deprecated pricing config endpoint', () => {
    expect((API_ENDPOINTS.PRICING as Record<string, unknown>).CONFIG).toBeUndefined()
  })

  it('calls admin logout via canonical route', async () => {
    const postSpy = jest.spyOn(apiClient, 'post').mockResolvedValue({} as never)

    await adminApiClient.logout()

    expect(postSpy).toHaveBeenCalledWith('/api/v1/admin/auth/logout')
  })

  it('uses PUT method and reason payload for user block/unblock', async () => {
    const putSpy = jest.spyOn(apiClient, 'put').mockResolvedValue({} as never)

    await adminApiClient.blockUser(7, 'Policy violation')
    await adminApiClient.unblockUser(7)

    expect(putSpy).toHaveBeenNthCalledWith(
      1,
      '/api/v1/admin/users/7/block',
      { reason: 'Policy violation' }
    )
    expect(putSpy).toHaveBeenNthCalledWith(2, '/api/v1/admin/users/7/unblock')
  })

  it('uses canonical admin elevation and bulk payload contract', async () => {
    const postSpy = jest.spyOn(apiClient, 'post').mockResolvedValue({} as never)

    await adminApiClient.makeAdmin(9, true, false)
    await adminApiClient.bulkUserAction([1, 2, 3], 'block')

    expect(postSpy).toHaveBeenNthCalledWith(
      1,
      '/api/v1/admin/users/9/make-admin',
      {
        is_admin: true,
        is_super_admin: false,
      }
    )
    expect(postSpy).toHaveBeenNthCalledWith(2, '/api/v1/admin/users/bulk', {
      user_ids: [1, 2, 3],
      action: 'block',
    })
  })

  it('uses canonical user refund read contracts', async () => {
    const getSpy = jest.spyOn(apiClient, 'get').mockResolvedValue({} as never)

    await refundsApiClient.listUserRefunds({ status: 'pending', page: 2, perPage: 15 })
    await refundsApiClient.getRefundRequest(55)

    expect(getSpy).toHaveBeenNthCalledWith(1, '/api/v1/refunds?status=pending&page=2&per_page=15')
    expect(getSpy).toHaveBeenNthCalledWith(2, '/api/v1/refunds/55')
  })

  it('records production case detector evidence via structured admin route', async () => {
    const postSpy = jest.spyOn(apiClient, 'post').mockResolvedValue({} as never)
    const payload = {
      detector_name: 'GPTZero',
      result_percent: 24,
      decision: 'passed' as const,
      artifact_format: 'docx' as const,
      checked_at: '2026-06-22T10:00:00Z',
      report_ref: 'docs/phase1-runs/RUN-001.md',
      reason: 'Phase 1 proof run detector evidence.',
    }

    await adminApiClient.recordDetectorResult(12, 'ai_detection_proxy', payload)

    expect(postSpy).toHaveBeenCalledWith(
      '/api/v1/admin/production-cases/12/release-gates/ai_detection_proxy/detector-result',
      payload
    )
  })
})
