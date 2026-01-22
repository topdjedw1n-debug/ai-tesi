/**
 * Playwright E2E Test Helpers
 *
 * Utilities for E2E testing:
 * - Mock authentication
 * - API route interception
 * - Common selectors
 * - Test data factories
 */

import { Page, expect } from '@playwright/test'

/**
 * Mock login helper (simulates magic link verification)
 *
 * Instead of real magic link flow, directly set auth tokens in localStorage
 * and navigate to dashboard. Faster and more reliable for E2E tests.
 */
export async function mockLogin(page: Page, email: string = 'test@example.com') {
  // Mock JWT tokens (backend validates these in real flow)
  const mockAccessToken = 'mock-access-token-' + Date.now()
  const mockRefreshToken = 'mock-refresh-token-' + Date.now()

  // Set tokens in localStorage (where AuthProvider reads them)
  await page.addInitScript((tokens: any) => {
    localStorage.setItem('auth_token', tokens.access)
    localStorage.setItem('refresh_token', tokens.refresh)
  }, { access: mockAccessToken, refresh: mockRefreshToken })

  // Navigate to dashboard (will load user from /api/v1/auth/me)
  await page.goto('/dashboard')

  // Wait for auth check to complete
  await page.waitForLoadState('networkidle')
}

/**
 * Mock API responses for specific endpoints
 *
 * Intercepts API calls and returns mock data instead of hitting real backend.
 * Useful when backend is unavailable or for testing specific scenarios.
 */
export async function mockApiRoute(
  page: Page,
  url: string | RegExp,
  response: any,
  status: number = 200
) {
  await page.route(url, (route) => {
    route.fulfill({
      status,
      contentType: 'application/json',
      body: JSON.stringify(response),
    })
  })
}

/**
 * Mock user data for /api/v1/auth/me endpoint
 */
export async function mockAuthMe(page: Page, userData?: any) {
  const defaultUser = {
    id: 1,
    email: 'test@example.com',
    full_name: 'Test User',
    is_active: true,
    is_admin: false,
    is_super_admin: false,
    created_at: new Date().toISOString(),
  }

  await mockApiRoute(
    page,
    '**/api/v1/auth/me',
    { ...defaultUser, ...userData }
  )
}

/**
 * Mock documents list for dashboard
 */
export async function mockDocumentsList(page: Page, documents?: any[]) {
  const defaultDocs = [
    {
      id: 1,
      title: 'AI Ethics Research',
      status: 'completed',
      pages: 25,
      language: 'en',
      created_at: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
    },
    {
      id: 2,
      title: 'Machine Learning Thesis',
      status: 'generating',
      pages: 50,
      language: 'en',
      created_at: new Date().toISOString(),
    },
  ]

  await mockApiRoute(
    page,
    '**/api/v1/documents',
    documents || defaultDocs
  )
}

/**
 * Mock dashboard stats
 */
export async function mockDashboardStats(page: Page, stats?: any) {
  const defaultStats = {
    total_documents: 5,
    completed: 3,
    in_progress: 1,
    failed: 1,
    total_spent: 125.50,
  }

  await mockApiRoute(
    page,
    '**/api/v1/documents/stats',
    { ...defaultStats, ...stats }
  )
}

/**
 * Fill document creation form
 */
export async function fillDocumentForm(
  page: Page,
  data: {
    title: string
    topic: string
    language?: string
    pages?: number
  }
) {
  await page.fill('[data-testid="document-title-input"]', data.title)
  await page.fill('[data-testid="document-topic-input"]', data.topic)

  if (data.language) {
    await page.selectOption('[data-testid="document-language-select"]', data.language)
  }

  if (data.pages) {
    await page.fill('[data-testid="document-pages-input"]', data.pages.toString())
  }
}

/**
 * Wait for toast notification to appear
 */
export async function waitForToast(page: Page, text?: string) {
  const toastSelector = '[data-testid="toast-notification"]'

  if (text) {
    await expect(page.locator(toastSelector)).toContainText(text)
  } else {
    await expect(page.locator(toastSelector)).toBeVisible()
  }
}

/**
 * Common test data factories
 */
export const testData = {
  validEmail: 'test@example.com',
  invalidEmail: 'invalid-email',

  document: {
    title: 'Test Document',
    topic: 'Artificial Intelligence in Healthcare',
    language: 'en',
    pages: 25,
  },

  user: {
    id: 1,
    email: 'test@example.com',
    full_name: 'Test User',
  },
}
