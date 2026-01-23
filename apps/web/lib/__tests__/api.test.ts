/**
 * Sanity test for API Client
 *
 * This test verifies that the API client module can be imported
 * and has the expected structure.
 */

import { apiClient, API_ENDPOINTS } from '../api'

describe('API Client - Sanity Check', () => {
  it('should import apiClient successfully', () => {
    expect(apiClient).toBeDefined()
  })

  it('should have all HTTP methods defined', () => {
    expect(apiClient.get).toBeDefined()
    expect(apiClient.post).toBeDefined()
    expect(apiClient.put).toBeDefined()
    expect(apiClient.delete).toBeDefined()

    expect(typeof apiClient.get).toBe('function')
    expect(typeof apiClient.post).toBe('function')
    expect(typeof apiClient.put).toBe('function')
    expect(typeof apiClient.delete).toBe('function')
  })

  it('should have API_ENDPOINTS defined', () => {
    expect(API_ENDPOINTS).toBeDefined()
    expect(API_ENDPOINTS.AUTH).toBeDefined()
    expect(API_ENDPOINTS.DOCUMENTS).toBeDefined()
    expect(API_ENDPOINTS.PAYMENT).toBeDefined()
  })

  it('should have correct endpoint structure for AUTH', () => {
    expect(API_ENDPOINTS.AUTH.MAGIC_LINK).toBe('/api/v1/auth/magic-link')
    expect(API_ENDPOINTS.AUTH.VERIFY_MAGIC_LINK).toBe('/api/v1/auth/verify-magic-link')
    expect(API_ENDPOINTS.AUTH.REFRESH).toBe('/api/v1/auth/refresh')
    expect(API_ENDPOINTS.AUTH.LOGOUT).toBe('/api/v1/auth/logout')
    expect(API_ENDPOINTS.AUTH.ME).toBe('/api/v1/auth/me')
  })

  it('should have correct endpoint structure for DOCUMENTS', () => {
    expect(API_ENDPOINTS.DOCUMENTS.LIST).toBe('/api/v1/documents')
    expect(API_ENDPOINTS.DOCUMENTS.CREATE).toBe('/api/v1/documents')
    expect(API_ENDPOINTS.DOCUMENTS.STATS).toBe('/api/v1/documents/stats')
    expect(API_ENDPOINTS.DOCUMENTS.ACTIVITY).toBe('/api/v1/documents/activity')

    // Test dynamic endpoints
    expect(typeof API_ENDPOINTS.DOCUMENTS.GET).toBe('function')
    expect(API_ENDPOINTS.DOCUMENTS.GET(123)).toBe('/api/v1/documents/123')

    expect(typeof API_ENDPOINTS.DOCUMENTS.UPDATE).toBe('function')
    expect(API_ENDPOINTS.DOCUMENTS.UPDATE(456)).toBe('/api/v1/documents/456')

    expect(typeof API_ENDPOINTS.DOCUMENTS.DELETE).toBe('function')
    expect(API_ENDPOINTS.DOCUMENTS.DELETE(789)).toBe('/api/v1/documents/789')

    expect(typeof API_ENDPOINTS.DOCUMENTS.EXPORT).toBe('function')
    expect(API_ENDPOINTS.DOCUMENTS.EXPORT(101)).toBe('/api/v1/documents/101/export')
  })
})
