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

export interface AdminDocumentListResponse {
  documents: AdminDocument[]
  total: number
  page: number
  per_page: number
  pages?: number
  total_pages?: number
}

export interface StuckJob {
  id: number
  user_id: number
  document_id: number
  job_type: string
  status: string
  started_at: string
  stuck_for_minutes: number
}

export interface StuckJobsResponse {
  stuck_jobs: {
    total: number
    queued_stuck: number
    running_stuck: number
  }
  queued_jobs: StuckJob[]
  running_jobs: StuckJob[]
  threshold_minutes: number
  monitored_at: string
  recommendations: {
    cleanup_needed: boolean
    message: string
  }
}

export interface CostAnalysisResponse {
  period: {
    start_date: string
    end_date: string
    group_by: string
  }
  totals: {
    total_cost_cents: number
    total_cost_eur_cents?: number
    total_tokens: number
    average_cost_per_token: number
  }
  generated_at: string
}

export interface ProductionCase {
  id: number
  document_id: number
  client_user_id: number
  manager_id: number | null
  editor_id: number | null
  deadline_at: string | null
  citation_style: string | null
  requirements_text: string | null
  intake_status: string
  generation_status: string
  qa_status: string
  editorial_status: string
  payment_status: string
  delivery_status: string
  release_status: string
  human_minutes_budget: number
  human_minutes_used: number
  cost_cents: number
  ai_total_tokens?: number
  ai_cost_usd_cents?: number
  ai_cost_eur_cents?: number
  release_notes: string | null
  released_at: string | null
  created_at: string | null
  updated_at: string | null
  document: {
    id: number
    title: string
    topic: string
    status: string
    language: string
    target_pages: number
    docx_path?: string | null
    pdf_path?: string | null
  } | null
  client_email: string | null
  manager_email: string | null
  editor_email: string | null
}

export interface ProductionCaseListResponse {
  cases: ProductionCase[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export interface ReleaseGate {
  id: number | null
  production_case_id: number
  gate_key: string
  status: 'passed' | 'failed' | 'warning' | 'unchecked' | 'no_data' | 'overridden' | string
  severity: string
  blocking: boolean
  source: string | null
  summary: string | null
  evidence: Record<string, any> | null
  override_allowed: boolean
  override_reason: string | null
  overridden_by_id: number | null
  overridden_at: string | null
  last_checked_at: string | null
}

export interface ManualDetectorResultPayload {
  detector_name: string
  result_percent: number
  threshold_percent: number
  checked_at: string
  report_ref: string
  reason: string
}

export interface EditorTask {
  id: number
  production_case_id: number
  document_id: number
  section_id: number | null
  assigned_editor_id: number
  created_by_id: number | null
  source_gate: string | null
  finding_key: string | null
  title: string
  description: string | null
  status: string
  resolution_notes: string | null
  minutes_spent: number
  resolved_at: string | null
  created_at: string | null
  updated_at: string | null
  document_title: string | null
  section_title: string | null
}

export interface EditorTaskListResponse {
  tasks: EditorTask[]
  total: number
  page: number
  per_page: number
  total_pages: number
}

export interface UserDetails {
  id: number
  email: string
  name: string | null
  is_active: boolean
  is_admin: boolean
  is_super_admin?: boolean // Optional super admin flag
  status?: 'active' | 'blocked' | 'deleted'
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

export interface UserListResponse {
  users: UserDetails[]
  total: number
  page: number
  per_page: number
  total_pages: number
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
  topic: string
  language: string
  target_pages: number
  status:
    | 'draft'
    | 'generating'
    | 'outline_generated'
    | 'sections_generated'
    | 'completed'
    | 'failed'
    | 'failed_quality'
    | 'payment_pending'
    | string
  pages: number
  word_count: number
  ai_provider: string
  ai_model: string
  tokens_used: number
  generation_time_seconds: number
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

const unwrapResponse = <T>(response: T | { data: T }): T => {
  if (response && typeof response === 'object' && 'data' in (response as object)) {
    return (response as { data: T }).data;
  }
  return response as T;
};

const toNumber = (value: unknown, fallback = 0): number => {
  if (typeof value === 'number' && Number.isFinite(value)) {
    return value
  }

  if (typeof value === 'string') {
    const parsed = Number(value)
    if (Number.isFinite(parsed)) {
      return parsed
    }
  }

  return fallback
}

const resolveIsActive = (raw: Record<string, unknown>): boolean => {
  if (typeof raw.is_active === 'boolean') {
    return raw.is_active
  }

  if (raw.status === 'blocked' || raw.status === 'deleted') {
    return false
  }

  return true
}

const resolveStatus = (
  rawStatus: unknown,
  isActive: boolean
): UserDetails['status'] => {
  if (rawStatus === 'active' || rawStatus === 'blocked' || rawStatus === 'deleted') {
    return rawStatus
  }

  return isActive ? 'active' : 'blocked'
}

const normalizeAdminUser = (rawUser: unknown): UserDetails => {
  const raw = (rawUser ?? {}) as Record<string, unknown>
  const createdAt = typeof raw.created_at === 'string'
    ? raw.created_at
    : typeof raw.registered_at === 'string'
      ? raw.registered_at
      : new Date(0).toISOString()

  const isActive = resolveIsActive(raw)
  const status = resolveStatus(raw.status, isActive)
  const totalSpentFromCostCents = toNumber(raw.total_cost, 0) / 100
  const totalSpent = raw.total_spent !== undefined
    ? toNumber(raw.total_spent, 0)
    : raw.total_paid !== undefined
      ? toNumber(raw.total_paid, 0)
      : totalSpentFromCostCents

  return {
    id: toNumber(raw.id, 0),
    email: typeof raw.email === 'string' ? raw.email : '',
    name:
      typeof raw.name === 'string'
        ? raw.name
        : typeof raw.full_name === 'string'
          ? raw.full_name
          : null,
    is_active: isActive,
    is_admin: Boolean(raw.is_admin),
    is_super_admin:
      typeof raw.is_super_admin === 'boolean' ? raw.is_super_admin : undefined,
    status,
    registered_at:
      typeof raw.registered_at === 'string' ? raw.registered_at : createdAt,
    last_login: typeof raw.last_login === 'string' ? raw.last_login : null,
    documents_count: toNumber(raw.documents_count ?? raw.total_documents_created, 0),
    total_spent: totalSpent,
    total_refunds: toNumber(raw.total_refunds, 0),
    created_at: createdAt,
    updated_at: typeof raw.updated_at === 'string' ? raw.updated_at : createdAt,
  }
}

export const adminApiClient = {
  /**
   * Admin login with email and password
   * @param {string} email - Admin email address
   * @param {string} password - Admin password
   * @returns {Promise<{access_token: string, user: object}>} Auth response with token
   */
  async simpleLogin(email: string, password: string) {
    const response = await apiClient.post('/api/v1/auth/admin-login', { email, password })
    return unwrapResponse(response)
  },

  async logout() {
    return apiClient.post('/api/v1/admin/auth/logout')
  },

  // Dashboard
  async getStats(): Promise<PlatformStats> {
    const response = await apiClient.get('/api/v1/admin/stats')
    return unwrapResponse(response)
  },

  async getCharts(period: string): Promise<DashboardCharts> {
    const url = buildUrlWithParams('/api/v1/admin/dashboard/charts', { period });
    const response = await apiClient.get(url)
    const data = unwrapResponse<any>(response)
    return {
      revenue: (data.revenue || []).map((item: any) => ({
        date: item.date,
        amount: item.amount ?? item.revenue ?? 0,
      })),
      users: (data.users || []).map((item: any) => ({
        date: item.date,
        count: item.count ?? item.new_users ?? 0,
      })),
      documents: (data.documents || []).map((item: any) => ({
        date: item.date,
        count: item.count ?? item.documents ?? 0,
      })),
    }
  },

  async getActivity(type: string, limit: number): Promise<DashboardActivity[]> {
    const url = buildUrlWithParams('/api/v1/admin/dashboard/activity', { type, limit });
    const response = await apiClient.get(url)
    const data = unwrapResponse<any>(response)
    const activities = Array.isArray(data) ? data : (data.activities || [])
    return activities.map((activity: any) => ({
      id: activity.id,
      type: activity.type ?? activity.action ?? 'activity',
      description: activity.description ?? activity.action ?? 'Activity',
      created_at: activity.created_at,
      timestamp: activity.timestamp ?? activity.created_at,
      amount: activity.amount,
      user_id: activity.user_id ?? activity.target_id,
      email: activity.email,
      error_message: activity.error_message,
      details: activity.details ?? activity.new_value ?? activity.old_value,
    }))
  },

  async getMetrics(): Promise<DashboardMetrics> {
    const response = await apiClient.get('/api/v1/admin/dashboard/metrics')
    return unwrapResponse(response)
  },

  // Users
  async getUsers(params: any): Promise<UserListResponse> {
    const url = buildUrlWithParams('/api/v1/admin/users', params);
    const response = await apiClient.get(url)
    const data = unwrapResponse<any>(response)
    const rawUsers = Array.isArray(data) ? data : Array.isArray(data?.users) ? data.users : []

    return {
      users: rawUsers.map(normalizeAdminUser),
      total: toNumber(data?.total, rawUsers.length),
      page: toNumber(data?.page, 1),
      per_page: toNumber(data?.per_page, rawUsers.length || 10),
      total_pages: toNumber(data?.total_pages, 1),
    }
  },

  async getUser(id: number): Promise<UserDetails> {
    const response = await apiClient.get(`/api/v1/admin/users/${id}`)
    return normalizeAdminUser(unwrapResponse(response))
  },

  async blockUser(id: number, reason = 'Blocked by admin') {
    return apiClient.put(`/api/v1/admin/users/${id}/block`, { reason })
  },

  async unblockUser(id: number) {
    return apiClient.put(`/api/v1/admin/users/${id}/unblock`)
  },

  async deleteUser(id: number) {
    return apiClient.delete(`/api/v1/admin/users/${id}`)
  },

  async makeAdmin(id: number, isAdmin: boolean, isSuperAdmin: boolean) {
    return apiClient.post(`/api/v1/admin/users/${id}/make-admin`, {
      is_admin: isAdmin,
      is_super_admin: isSuperAdmin,
    })
  },

  async bulkUserAction(ids: number[], action: string) {
    return apiClient.post('/api/v1/admin/users/bulk', { user_ids: ids, action })
  },

  // Documents
  async getDocuments(params: any): Promise<AdminDocumentListResponse> {
    const url = buildUrlWithParams('/api/v1/admin/documents', params);
    const response = await apiClient.get(url)
    return unwrapResponse(response)
  },

  async getDocument(id: number): Promise<AdminDocument> {
    const response = await apiClient.get(`/api/v1/admin/documents/${id}`)
    return unwrapResponse(response)
  },

  async getDocumentLogs(id: number) {
    const response = await apiClient.get(`/api/v1/admin/documents/${id}/logs`)
    return unwrapResponse(response)
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

  async getStuckJobs(thresholdMinutes = 5): Promise<StuckJobsResponse> {
    const url = buildUrlWithParams('/api/v1/admin/jobs/stuck', {
      threshold_minutes: thresholdMinutes,
    })
    const response = await apiClient.get(url)
    return unwrapResponse(response)
  },

  async getCosts(params?: {
    start_date?: string
    end_date?: string
    group_by?: 'day' | 'week' | 'month'
  }): Promise<CostAnalysisResponse> {
    const url = buildUrlWithParams('/api/v1/admin/costs', params)
    const response = await apiClient.get(url)
    return unwrapResponse(response)
  },

  async getProductionCases(params?: {
    page?: number
    per_page?: number
    release_status?: string
    manager_id?: number
    editor_id?: number
  }): Promise<ProductionCaseListResponse> {
    const url = buildUrlWithParams('/api/v1/admin/production-cases', params)
    const response = await apiClient.get(url)
    return unwrapResponse(response)
  },

  async createProductionCase(payload: {
    document_id: number
    manager_id?: number
    editor_id?: number
    deadline_at?: string
    citation_style?: string
    requirements_text?: string
  }): Promise<ProductionCase> {
    const response = await apiClient.post('/api/v1/admin/production-cases', payload)
    return unwrapResponse(response)
  },

  async getProductionCase(id: number): Promise<ProductionCase> {
    const response = await apiClient.get(`/api/v1/admin/production-cases/${id}`)
    return unwrapResponse(response)
  },

  async updateProductionCase(
    id: number,
    payload: Partial<ProductionCase>
  ): Promise<ProductionCase> {
    const response = await apiClient.patch(
      `/api/v1/admin/production-cases/${id}`,
      payload
    )
    return unwrapResponse(response)
  },

  async getReleaseGates(caseId: number): Promise<ReleaseGate[]> {
    const response = await apiClient.get(
      `/api/v1/admin/production-cases/${caseId}/release-gates`
    )
    return unwrapResponse(response)
  },

  async overrideReleaseGate(
    caseId: number,
    gateKey: string,
    reason: string
  ): Promise<ReleaseGate> {
    const response = await apiClient.post(
      `/api/v1/admin/production-cases/${caseId}/release-gates/${gateKey}/override`,
      { reason }
    )
    return unwrapResponse(response)
  },

  async recordDetectorResult(
    caseId: number,
    gateKey: string,
    payload: ManualDetectorResultPayload
  ): Promise<ReleaseGate> {
    const response = await apiClient.post(
      `/api/v1/admin/production-cases/${caseId}/release-gates/${gateKey}/detector-result`,
      payload
    )
    return unwrapResponse(response)
  },

  async releaseProductionCase(caseId: number, notes?: string): Promise<ProductionCase> {
    const response = await apiClient.post(
      `/api/v1/admin/production-cases/${caseId}/release`,
      { notes }
    )
    return unwrapResponse(response)
  },

  async createEditorTask(
    caseId: number,
    payload: {
      production_case_id?: number
      assigned_editor_id: number
      section_id?: number
      source_gate?: string
      finding_key?: string
      title: string
      description?: string
    }
  ): Promise<EditorTask> {
    const response = await apiClient.post(
      `/api/v1/admin/production-cases/${caseId}/editor-tasks`,
      { ...payload, production_case_id: caseId }
    )
    return unwrapResponse(response)
  },

  async getEditorTasks(params?: {
    page?: number
    per_page?: number
    status?: string
  }): Promise<EditorTaskListResponse> {
    const url = buildUrlWithParams('/api/v1/editor/tasks', params)
    const response = await apiClient.get(url)
    return unwrapResponse(response)
  },

  async getEditorTask(id: number): Promise<EditorTask> {
    const response = await apiClient.get(`/api/v1/editor/tasks/${id}`)
    return unwrapResponse(response)
  },

  async resolveEditorTask(
    id: number,
    payload: { resolution_notes: string; minutes_spent: number; status?: string }
  ): Promise<EditorTask> {
    const response = await apiClient.post(
      `/api/v1/editor/tasks/${id}/resolve`,
      payload
    )
    return unwrapResponse(response)
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
    return unwrapResponse(response)
  },

  async getPaymentStripeLink(id: number) {
    const response = await apiClient.get(`/api/v1/admin/payments/${id}/stripe-link`)
    return unwrapResponse(response)
  },

  async initiatePaymentRefund(id: number) {
    return apiClient.post(`/api/v1/admin/payments/${id}/refund`)
  },

  async exportPayments(format: string, params: any): Promise<Blob> {
    const url = buildUrlWithParams('/api/v1/admin/payments/export', { ...params, format });
    const response = await apiClient.get(url)
    return unwrapResponse(response)
  },

  // Refunds
  async getRefunds(params: any) {
    const url = buildUrlWithParams('/api/v1/admin/refunds', params);
    return apiClient.get(url)
  },

  async getRefund(id: number): Promise<RefundRequest> {
    const response = await apiClient.get(`/api/v1/admin/refunds/${id}`)
    return unwrapResponse(response)
  },

  async getRefundStats() {
    const response = await apiClient.get('/api/v1/admin/refunds/stats')
    return unwrapResponse(response)
  },

  async getPendingRefunds() {
    const response = await apiClient.get('/api/v1/admin/refunds/pending')
    return unwrapResponse(response)
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
    return unwrapResponse(response)
  },

  // Settings
  async getAllSettings() {
    const response = await apiClient.get('/api/v1/admin/settings')
    return unwrapResponse(response)
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
