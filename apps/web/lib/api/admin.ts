/**
 * Admin API types and interfaces
 */

export interface PlatformStats {
  total_users: number
  active_users_today: number
  total_revenue: number
  revenue_today: number
  total_documents: number
  completed_documents: number
  pending_refunds: number
  active_jobs: number
}

export interface UserDetails {
  id: number
  email: string
  name: string | null
  is_admin: boolean
  is_super_admin?: boolean // Optional super admin flag
  status: 'active' | 'blocked' | 'deleted'
  registered_at: string
  last_login: string | null
  documents_count: number
  total_spent: number
  total_refunds?: number
  created_at: string
  updated_at: string
  documents?: AdminDocument[] // Optional for user details page
  payments?: any[] // Optional for user details page
}

/** Alias for AdminUser (backwards compatibility) */
export type AdminUser = UserDetails

export interface RefundRequest {
  id: number
  payment_id: number
  user_id: number
  user_email: string
  document_id: number
  document_title: string
  amount: number
  reason: string
  reason_category?: string // Category of refund reason
  status: 'pending' | 'approved' | 'rejected'
  created_at: string
  submitted_at?: string // When refund was submitted
  updated_at: string
  reviewed_by: number | null
  reviewed_at: string | null
  admin_notes: string | null
  admin_comment?: string // Admin review comment
  refund_amount?: number // Actual refund amount (may differ from requested)
  screenshots?: string[] // URLs of uploaded screenshots
  // Optional nested objects for RefundReviewForm component
  payment?: {
    id: number
    amount: number
    currency: string
    created_at: string
    status?: string
  }
  user?: {
    id: number
    email: string
    registered_at: string
  }
  risk_score?: number | null // AI risk analysis (0-1)
  ai_recommendation?: 'approve' | 'reject' | 'review'
}

/** Alias for RefundRequest with full details */
export type RefundDetails = RefundRequest

export interface RefundStats {
  total: number
  pending: number
  approved: number
  rejected: number
  total_amount: number
  approved_amount: number
  rejected_amount: number
  total_requests: number
  approval_rate: number
  total_refunded_amount: number
  average_processing_time_hours: number
}

export interface PricingSettings {
  price_per_page: number
  currency: string
  min_pages: number
  max_pages: number
  currencies?: string[] // Optional supported currencies list
}

export interface AISettings {
  default_provider: string
  default_model?: string
  available_models: string[]
  fallback_models?: string[]
  max_tokens: number
  max_retries?: number
  timeout_seconds?: number
  temperature: number
  temperature_default?: number
}

export interface LimitSettings {
  max_concurrent_generations?: number
  max_documents_per_user: number
  max_pages_per_document: number
  daily_token_limit?: number | null
  rate_limit_per_minute: number
}

export interface MaintenanceSettings {
  maintenance_mode: boolean
  enabled?: boolean // Alias for maintenance_mode
  maintenance_message: string
  message?: string // Alias for maintenance_message
  allowed_ips?: string[]
  estimated_end_time?: string | null
}

export interface AdminDocument {
  id: number
  user_id: number
  user_email: string
  title: string
  status: 'draft' | 'outline_generated' | 'sections_generated' | 'completed' | 'failed'
  pages: number
  word_count: number
  created_at: string
  completed_at: string | null
  error_message: string | null
}

export interface DashboardCharts {
  revenue: Array<{ date: string; amount: number }>
  users: Array<{ date: string; count: number }>
  documents: Array<{ date: string; count: number }>
}

export interface DashboardActivity {
  id: number
  type: string
  description: string
  created_at: string
  timestamp?: string // Alias for created_at (backwards compatibility)
  amount?: number // For payment activities
  user_id?: number // For user-related activities
  email?: string // For registration activities
  error_message?: string // For error activities
  details?: string // Generic details field
}

/** Alias for DashboardActivity (backwards compatibility) */
export type ActivityItem = DashboardActivity

export interface DashboardMetrics {
  conversion_rate: number
  avg_revenue_per_user: number
  avg_document_pages: number
  completion_rate: number
  mrr: number
  arpu: number
  churn_rate: number
  refund_rate: number
}

/**
 * Admin API Client
 *
 * Centralized API client for admin panel operations.
 * Requires admin authentication (admin session in localStorage).
 *
 * @module admin-api
 * @example
 * ```tsx
 * import { adminApiClient } from '@/lib/api/admin'
 *
 * // Get platform statistics
 * const stats = await adminApiClient.getStats()
 *
 * // Block a user
 * await adminApiClient.blockUser(userId)
 * ```
 */
import { apiClient } from '../api'

// Helper to build URL with query params
const buildUrlWithParams = (baseUrl: string, params?: Record<string, any>): string => {
  if (!params) return baseUrl;
  const searchParams = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value));
    }
  });
  const queryString = searchParams.toString();
  return queryString ? `${baseUrl}?${queryString}` : baseUrl;
};

export const adminApiClient = {
  /**
   * Admin login with email and password
   * @param {string} email - Admin email address
   * @param {string} password - Admin password
   * @returns {Promise<{access_token: string, user: object}>} Auth response with token
   */
  async simpleLogin(email: string, password: string) {
    const response = await apiClient.post('/api/v1/auth/admin-login', { email, password })
    return response.data
  },

  async logout() {
    return apiClient.post('/api/v1/auth/admin-logout')
  },

  // Dashboard
  async getStats(): Promise<PlatformStats> {
    const response = await apiClient.get('/api/v1/admin/stats')
    return response.data
  },

  async getCharts(period: string): Promise<DashboardCharts> {
    const url = buildUrlWithParams('/api/v1/admin/dashboard/charts', { period });
    const response = await apiClient.get(url)
    return response.data
  },

  async getActivity(type: string, limit: number): Promise<DashboardActivity[]> {
    const url = buildUrlWithParams('/api/v1/admin/dashboard/activity', { type, limit });
    const response = await apiClient.get(url)
    return response.data
  },

  async getMetrics(): Promise<DashboardMetrics> {
    const response = await apiClient.get('/api/v1/admin/dashboard/metrics')
    return response.data
  },

  // Users
  async getUsers(params: any) {
    const url = buildUrlWithParams('/api/v1/admin/users', params);
    return apiClient.get(url)
  },

  async getUser(id: number): Promise<UserDetails> {
    const response = await apiClient.get(`/api/v1/admin/users/${id}`)
    return response.data
  },

  async blockUser(id: number) {
    return apiClient.post(`/api/v1/admin/users/${id}/block`)
  },

  async unblockUser(id: number) {
    return apiClient.post(`/api/v1/admin/users/${id}/unblock`)
  },

  async deleteUser(id: number) {
    return apiClient.delete(`/api/v1/admin/users/${id}`)
  },

  async makeAdmin(id: number, isAdmin: boolean, isSuperAdmin: boolean) {
    return apiClient.post(`/api/v1/admin/users/${id}/admin`, { is_admin: isAdmin, is_super_admin: isSuperAdmin })
  },

  async bulkUserAction(ids: number[], action: string) {
    return apiClient.post('/api/v1/admin/users/bulk', { ids, action })
  },

  // Documents
  async getDocuments(params: any) {
    const url = buildUrlWithParams('/api/v1/admin/documents', params);
    return apiClient.get(url)
  },

  async getDocument(id: number): Promise<AdminDocument> {
    const response = await apiClient.get(`/api/v1/admin/documents/${id}`)
    return response.data
  },

  async getDocumentLogs(id: number) {
    const response = await apiClient.get(`/api/v1/admin/documents/${id}/logs`)
    return response.data
  },

  async deleteDocument(id: number) {
    return apiClient.delete(`/api/v1/admin/documents/${id}`)
  },

  async retryDocument(id: number) {
    return apiClient.post(`/api/v1/admin/documents/${id}/retry`)
  },

  async getUserDocuments(userId: number, page = 1, limit = 10) {
    const url = buildUrlWithParams(`/api/v1/admin/users/${userId}/documents`, { page, limit });
    return apiClient.get(url)
  },

  // Payments
  async getPayments(params: any) {
    const url = buildUrlWithParams('/api/v1/admin/payments', params);
    return apiClient.get(url)
  },

  async getUserPayments(userId: number, page = 1, limit = 10) {
    const url = buildUrlWithParams(`/api/v1/admin/users/${userId}/payments`, { page, limit });
    return apiClient.get(url)
  },

  async getPayment(id: number) {
    const response = await apiClient.get(`/api/v1/admin/payments/${id}`)
    return response.data
  },

  async getPaymentStripeLink(id: number) {
    const response = await apiClient.get(`/api/v1/admin/payments/${id}/stripe-link`)
    return response.data
  },

  async initiatePaymentRefund(id: number) {
    return apiClient.post(`/api/v1/admin/payments/${id}/refund`)
  },

  async exportPayments(format: string, params: any): Promise<Blob> {
    const url = buildUrlWithParams('/api/v1/admin/payments/export', { ...params, format });
    const response = await apiClient.get(url)
    return response.data
  },

  // Refunds
  async getRefunds(params: any) {
    const url = buildUrlWithParams('/api/v1/admin/refunds', params);
    return apiClient.get(url)
  },

  async getRefund(id: number): Promise<RefundRequest> {
    const response = await apiClient.get(`/api/v1/admin/refunds/${id}`)
    return response.data
  },

  async getRefundStats() {
    const response = await apiClient.get('/api/v1/admin/refunds/stats')
    return response.data
  },

  async getPendingRefunds() {
    const response = await apiClient.get('/api/v1/admin/refunds/pending')
    return response.data
  },

  async approveRefund(id: number, adminComment: string, processImmediately: boolean) {
    return apiClient.post(`/api/v1/admin/refunds/${id}/approve`, {
      admin_comment: adminComment,
      process_immediately: processImmediately,
    })
  },

  async rejectRefund(id: number, adminComment: string) {
    return apiClient.post(`/api/v1/admin/refunds/${id}/reject`, { admin_comment: adminComment })
  },

  async analyzeRefund(id: number) {
    const response = await apiClient.get(`/api/v1/admin/refunds/${id}/analyze`)
    return response.data
  },

  // Settings
  async getAllSettings() {
    const response = await apiClient.get('/api/v1/admin/settings')
    return response.data
  },

  async updatePricingSettings(settings: any) {
    return apiClient.put('/api/v1/admin/settings/pricing', settings)
  },

  async updateAISettings(settings: any) {
    return apiClient.put('/api/v1/admin/settings/ai', settings)
  },

  async updateLimitSettings(settings: any) {
    return apiClient.put('/api/v1/admin/settings/limits', settings)
  },

  async updateMaintenanceSettings(settings: any) {
    return apiClient.put('/api/v1/admin/settings/maintenance', settings)
  },
}
