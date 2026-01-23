/**
 * Refunds API client for user-initiated refund requests
 *
 * @module refunds-api
 * @example
 * ```tsx
 * import { refundsApiClient } from '@/lib/api/refunds'
 *
 * // Create refund request
 * await refundsApiClient.createRefundRequest({
 *   payment_id: 123,
 *   reason: 'Not satisfied with quality',
 *   reason_category: 'quality',
 *   screenshots: ['url1', 'url2']
 * })
 * ```
 */

import { apiClient } from '../api'

/**
 * Data required to create a new refund request
 * @interface RefundRequestCreate
 */
export interface RefundRequestCreate {
  /** Payment ID to refund */
  payment_id: number
  /** Detailed reason for refund (min 10 chars) */
  reason: string
  /** Category of refund reason */
  reason_category: 'quality' | 'not_satisfied' | 'technical_issue' | 'other'
  /** Optional screenshot URLs as evidence */
  screenshots?: string[]
}

/**
 * Refund request data returned from API
 * @interface RefundRequest
 */
export interface RefundRequest {
  id: number
  payment_id: number
  user_id: number
  reason: string
  reason_category: string
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  updated_at: string
  reviewed_by: number | null
  reviewed_at: string | null
  admin_notes: string | null
}

export const refundsApiClient = {
  /**
   * Create a new refund request
   */
  async createRefundRequest(data: RefundRequestCreate): Promise<RefundRequest> {
    const response = await apiClient.post('/api/v1/refunds', data)
    return response.data
  },

  /**
   * Get refund request by ID
   */
  async getRefundRequest(id: number): Promise<RefundRequest> {
    const response = await apiClient.get(`/api/v1/refunds/${id}`)
    return response.data
  },

  /**
   * Get all refund requests for current user
   */
  async listUserRefunds(): Promise<RefundRequest[]> {
    const response = await apiClient.get('/api/v1/refunds')
    return response.data
  },
}
