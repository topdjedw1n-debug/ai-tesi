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
import { isUserRefundFlowEnabled } from '../feature-flags'

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
  submitted_at: string
  reviewed_at: string | null
  reviewed_by: number | null
  admin_comment: string | null
  refund_amount?: number | string | null
  ai_recommendation?: 'approve' | 'reject' | 'review' | null
  risk_score?: number | null
  screenshots?: string[]
  /** Backward compatibility for legacy UI fields */
  admin_notes?: string | null
}

export interface RefundListResponse {
  refunds: RefundRequest[]
  total: number
  page: number
  per_page: number
  pages: number
}

const REFUND_FLOW_DISABLED_MESSAGE =
  'Refund flow is temporarily disabled. Please contact support if needed.'

const ensureRefundFlowEnabled = () => {
  if (!isUserRefundFlowEnabled) {
    // ⚠️ Kill-switch: feature flag can disable user refund flow during incident mitigation.
    throw new Error(REFUND_FLOW_DISABLED_MESSAGE)
  }
}

export const refundsApiClient = {
  /**
   * Create a new refund request
   */
  async createRefundRequest(data: RefundRequestCreate): Promise<RefundRequest> {
    ensureRefundFlowEnabled()
    return apiClient.post('/api/v1/refunds', data)
  },

  /**
   * Get refund request by ID
   */
  async getRefundRequest(id: number): Promise<RefundRequest> {
    ensureRefundFlowEnabled()
    return apiClient.get(`/api/v1/refunds/${id}`)
  },

  /**
   * Get all refund requests for current user
   */
  async listUserRefunds(params?: {
    status?: 'pending' | 'approved' | 'rejected'
    page?: number
    perPage?: number
  }): Promise<RefundListResponse> {
    ensureRefundFlowEnabled()
    const search = new URLSearchParams()
    if (params?.status) {
      search.set('status', params.status)
    }
    if (params?.page) {
      search.set('page', String(params.page))
    }
    if (params?.perPage) {
      search.set('per_page', String(params.perPage))
    }
    const query = search.toString()
    const url = query ? `/api/v1/refunds?${query}` : '/api/v1/refunds'
    return apiClient.get(url)
  },

  getFallbackMessage(): string {
    return REFUND_FLOW_DISABLED_MESSAGE
  },
}
