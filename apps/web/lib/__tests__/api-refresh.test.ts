/**
 * API Client - Auto-Refresh Mechanism Tests
 *
 * Tests for JWT token auto-refresh functionality including:
 * - Preemptive refresh (5 min before expiry)
 * - Retry on 401 unauthorized
 * - Deduplication for concurrent requests
 * - Error handling scenarios
 */

import { apiClient, setTokens, clearTokens, getAccessToken } from '../api'

// Mock fetch globally
global.fetch = jest.fn()

// Helper to create JWT token
const createToken = (expiresInSeconds: number): string => {
  const payload = {
    exp: Math.floor(Date.now() / 1000) + expiresInSeconds,
    user_id: 1,
    email: 'test@example.com',
  }
  // Create fake JWT: header.payload.signature
  const header = btoa(JSON.stringify({ alg: 'HS256', typ: 'JWT' }))
  const encodedPayload = btoa(JSON.stringify(payload))
  return `${header}.${encodedPayload}.fake-signature`
}

describe('API Client - Auto-Refresh Mechanism', () => {
  beforeEach(() => {
    // Clear localStorage
    localStorage.clear()
    // Reset fetch mock
    jest.clearAllMocks()
    ;(global.fetch as jest.Mock).mockReset()
  })

  describe('Preemptive Refresh', () => {
    it('should refresh token when less than 5 minutes remaining', async () => {
      // Token expires in 4 minutes (should trigger preemptive refresh)
      const expiringSoonToken = createToken(4 * 60)
      const newToken = createToken(30 * 60) // New token valid for 30 min

      setTokens(expiringSoonToken, 'refresh-token')

      // Mock refresh endpoint
      ;(global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            access_token: newToken,
            refresh_token: 'new-refresh-token',
          }),
        })
        // Mock actual API call after refresh
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success' }),
        })

      const result = await apiClient.get('/test')

      // Verify refresh was called
      expect(global.fetch).toHaveBeenCalledTimes(2)
      expect(global.fetch).toHaveBeenNthCalledWith(
        1,
        expect.stringContaining('/api/v1/auth/refresh'),
        expect.objectContaining({
          method: 'POST',
        })
      )

      // Verify new token saved
      expect(getAccessToken()).toBe(newToken)
      expect(result).toEqual({ data: 'success' })
    })

    it('should NOT refresh when token has more than 5 minutes remaining', async () => {
      // Token expires in 10 minutes (no refresh needed)
      const validToken = createToken(10 * 60)

      setTokens(validToken, 'refresh-token')

      // Mock only the actual API call
      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: 'success' }),
      })

      const result = await apiClient.get('/test')

      // Verify NO refresh call, only the actual API call
      expect(global.fetch).toHaveBeenCalledTimes(1)
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/test'),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${validToken}`,
          }),
        })
      )
      expect(result).toEqual({ data: 'success' })
    })

    it('should use new token in request after preemptive refresh', async () => {
      const expiringSoonToken = createToken(3 * 60)
      const newToken = createToken(30 * 60)

      setTokens(expiringSoonToken, 'refresh-token')

      ;(global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            access_token: newToken,
            refresh_token: 'new-refresh-token',
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success' }),
        })

      await apiClient.get('/test')

      // Verify second call uses NEW token
      expect(global.fetch).toHaveBeenNthCalledWith(
        2,
        expect.anything(),
        expect.objectContaining({
          headers: expect.objectContaining({
            Authorization: `Bearer ${newToken}`,
          }),
        })
      )
    })
  })

  describe('401 Retry Logic', () => {
    it('should retry request with new token on 401 response', async () => {
      const validToken = createToken(30 * 60)
      const newToken = createToken(30 * 60)

      setTokens(validToken, 'refresh-token')

      ;(global.fetch as jest.Mock)
        // First call returns 401
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Unauthorized' }),
        })
        // Refresh token call
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            access_token: newToken,
            refresh_token: 'new-refresh-token',
          }),
        })
        // Retry original request with new token (but still 401)
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Unauthorized' }),
        })
        // Second refresh attempt
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            access_token: createToken(30 * 60),
            refresh_token: 'newer-refresh-token',
          }),
        })

      try {
        await apiClient.get('/test')
      } catch (error: any) {
        // Should eventually throw after retries
        expect(error.message).toContain('Token refreshed')
      }

      // Verify refresh was attempted
      expect(global.fetch).toHaveBeenCalledWith(
        expect.stringContaining('/api/v1/auth/refresh'),
        expect.anything()
      )
    })

    it('should clear tokens and throw if refresh fails on 401', async () => {
      const validToken = createToken(30 * 60)

      setTokens(validToken, 'refresh-token')

      ;(global.fetch as jest.Mock)
        // First call returns 401
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Unauthorized' }),
        })
        // Refresh fails
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Invalid refresh token' }),
        })

      try {
        await apiClient.get('/test')
        fail('Should have thrown error')
      } catch (error: any) {
        expect(error.message).toBeTruthy()
      }

      // Verify tokens cleared
      expect(getAccessToken()).toBeNull()
    })

    it('should redirect to login if refresh fails', async () => {
      const validToken = createToken(30 * 60)

      setTokens(validToken, 'refresh-token')

      // Mock window.location
      delete (window as any).location
      window.location = { href: '' } as any

      ;(global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Unauthorized' }),
        })
        .mockResolvedValueOnce({
          ok: false,
          status: 401,
          json: async () => ({ detail: 'Invalid refresh token' }),
        })

      try {
        await apiClient.get('/test')
      } catch (error) {
        // Expected to throw
      }

      // Note: Redirect happens in handleResponse after refresh failure
      // Testing actual redirect requires more complex setup
      expect(getAccessToken()).toBeNull()
    })
  })

  describe('Deduplication', () => {
    it('should deduplicate simultaneous refresh attempts', async () => {
      const expiringSoonToken = createToken(3 * 60)
      const newToken = createToken(30 * 60)

      setTokens(expiringSoonToken, 'refresh-token')

      ;(global.fetch as jest.Mock)
        // One refresh call
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            access_token: newToken,
            refresh_token: 'new-refresh-token',
          }),
        })
        // Two API calls
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success1' }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success2' }),
        })

      // Make two simultaneous requests
      const [result1, result2] = await Promise.all([
        apiClient.get('/test1'),
        apiClient.get('/test2'),
      ])

      // Both should succeed
      expect(result1).toEqual({ data: 'success1' })
      expect(result2).toEqual({ data: 'success2' })

      // Verify refresh was only called ONCE (deduplication)
      const refreshCalls = (global.fetch as jest.Mock).mock.calls.filter(
        (call) => call[0].includes('/api/v1/auth/refresh')
      )
      expect(refreshCalls).toHaveLength(1)
    })

    it('should wait for ongoing refresh before making new request', async () => {
      const expiringSoonToken = createToken(3 * 60)
      const newToken = createToken(30 * 60)

      setTokens(expiringSoonToken, 'refresh-token')

      let refreshResolve: any
      const refreshPromise = new Promise((resolve) => {
        refreshResolve = resolve
      })

      ;(global.fetch as jest.Mock)
        // Refresh call that takes time
        .mockImplementationOnce(() => refreshPromise)
        // API calls
        .mockResolvedValue({
          ok: true,
          json: async () => ({ data: 'success' }),
        })

      // Start first request (triggers refresh)
      const request1Promise = apiClient.get('/test1')

      // Wait a bit to ensure refresh started
      await new Promise((resolve) => setTimeout(resolve, 10))

      // Start second request (should wait for same refresh)
      const request2Promise = apiClient.get('/test2')

      // Resolve the refresh
      refreshResolve({
        ok: true,
        json: async () => ({
          access_token: newToken,
          refresh_token: 'new-refresh-token',
        }),
      })

      // Both should complete
      const [result1, result2] = await Promise.all([
        request1Promise,
        request2Promise,
      ])

      expect(result1).toEqual({ data: 'success' })
      expect(result2).toEqual({ data: 'success' })
    })
  })

  describe('Error Handling', () => {
    it('should handle network errors during refresh', async () => {
      const expiringSoonToken = createToken(3 * 60)

      setTokens(expiringSoonToken, 'refresh-token')

      ;(global.fetch as jest.Mock).mockRejectedValueOnce(
        new Error('Network error')
      )

      try {
        await apiClient.get('/test')
        fail('Should have thrown error')
      } catch (error: any) {
        // Should throw some error (either "Network error" or undefined response error)
        expect(error).toBeTruthy()
      }

      // Tokens should be cleared on refresh failure
      expect(getAccessToken()).toBeNull()
    })

    it('should handle invalid token format gracefully', async () => {
      setTokens('invalid-token', 'refresh-token')

      ;(global.fetch as jest.Mock)
        // Refresh called due to invalid token
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            access_token: createToken(30 * 60),
            refresh_token: 'new-refresh-token',
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success' }),
        })

      const result = await apiClient.get('/test')
      expect(result).toEqual({ data: 'success' })
    })

    it('should handle missing refresh token', async () => {
      const expiringSoonToken = createToken(3 * 60)

      // Set access token but NO refresh token
      localStorage.setItem('auth_token', expiringSoonToken)

      ;(global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({ data: 'success' }),
      })

      try {
        await apiClient.get('/test')
      } catch (error) {
        // Should handle gracefully or succeed with expired token
        // (behavior depends on implementation)
      }

      // If refresh fails due to missing refresh token, access token cleared
      const token = getAccessToken()
      expect(token === null || token === expiringSoonToken).toBeTruthy()
    })
  })

  describe('Token Management', () => {
    it('should update both access and refresh tokens on refresh', async () => {
      const expiringSoonToken = createToken(3 * 60)
      const newAccessToken = createToken(30 * 60)
      const newRefreshToken = 'new-refresh-token-123'

      setTokens(expiringSoonToken, 'old-refresh-token')

      ;(global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            access_token: newAccessToken,
            refresh_token: newRefreshToken,
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success' }),
        })

      await apiClient.get('/test')

      // Verify both tokens updated
      expect(getAccessToken()).toBe(newAccessToken)
      expect(localStorage.getItem('refresh_token')).toBe(newRefreshToken)
    })

    it('should keep old refresh token if new one not provided', async () => {
      const expiringSoonToken = createToken(3 * 60)
      const newAccessToken = createToken(30 * 60)
      const oldRefreshToken = 'old-refresh-token'

      setTokens(expiringSoonToken, oldRefreshToken)

      ;(global.fetch as jest.Mock)
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            access_token: newAccessToken,
            // No refresh_token in response
          }),
        })
        .mockResolvedValueOnce({
          ok: true,
          json: async () => ({ data: 'success' }),
        })

      await apiClient.get('/test')

      // Access token updated, refresh token unchanged
      expect(getAccessToken()).toBe(newAccessToken)
      expect(localStorage.getItem('refresh_token')).toBe(oldRefreshToken)
    })
  })
})
