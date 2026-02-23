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
  created_at: string
  updated_at: string
  reviewed_by: number | null
  reviewed_at: string | null
  admin_notes: string | null
}

const REFUNDS_READ_FALLBACK_MESSAGE =
  'Refund status lookup is temporarily unavailable. Please contact support if needed.'

export const refundsApiClient = {
  /**
   * Create a new refund request
   */
  async createRefundRequest(data: RefundRequestCreate): Promise<RefundRequest> {
    if (!isUserRefundFlowEnabled) {
      // ⚠️ TEMPORARY (pre-prod hardening): disable unstable user refund flow.
      // See /docs/MVP_PLAN.md → "Тимчасові рішення" (refund flow feature flag).
      // TODO: Remove this gate after backend/user flow runtime verification (Priority: 🔴 HIGH, Time: 2-4h)
      throw new Error(REFUNDS_READ_FALLBACK_MESSAGE)
    }
    return apiClient.post('/api/v1/refunds', data)
  },

  /**
   * Get refund request by ID
   */
  async getRefundRequest(id: number): Promise<RefundRequest | null> {
    // ⚠️ TEMPORARY (Wave 1): User read endpoints are not available on backend.
    // See /docs/MVP_PLAN.md → "Тимчасові рішення" (refunds read fallback).
    // TODO: Replace with real GET /api/v1/refunds/{id} once backend endpoint is implemented (Priority: 🟡 MEDIUM, Time: 2-3h)
    console.warn(`${REFUNDS_READ_FALLBACK_MESSAGE} Requested refund id=${id}`)
    return null
  },

  /**
   * Get all refund requests for current user
   */
  async listUserRefunds(): Promise<RefundRequest[]> {
    // ⚠️ TEMPORARY (Wave 1): User read endpoints are not available on backend.
    // See /docs/MVP_PLAN.md → "Тимчасові рішення" (refunds read fallback).
    // TODO: Replace with real GET /api/v1/refunds once backend endpoint is implemented (Priority: 🟡 MEDIUM, Time: 2-3h)
    console.warn(REFUNDS_READ_FALLBACK_MESSAGE)
    return []
  },

  getFallbackMessage(): string {
    return REFUNDS_READ_FALLBACK_MESSAGE
  },
}
