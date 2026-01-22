/**
 * E2E Test: Dashboard Stats Display
 *
 * Tests dashboard statistics and overview:
 * 1. User logs in and lands on dashboard
 * 2. Dashboard loads stats from API
 * 3. Stats cards display correct values:
 *    - Total documents
 *    - Completed documents
 *    - In progress
 *    - Total spent
 * 4. Recent activity list shows latest events
 */

import { test, expect } from '@playwright/test'
import { mockLogin, mockAuthMe, mockApiRoute, mockDashboardStats, testData } from './helpers'

test.describe('Dashboard Stats Display', () => {
  const mockStats = {
    total_documents: 12,
    completed: 8,
    in_progress: 2,
    failed: 2,
    total_spent: 245.50,
  }

  const mockRecentActivity = [
    {
      id: 1,
      action: 'document_completed',
      document_title: 'AI Ethics Research',
      timestamp: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
    },
    {
      id: 2,
      action: 'payment_processed',
      amount: 25.00,
      timestamp: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
    },
    {
      id: 3,
      action: 'document_created',
      document_title: 'Machine Learning Thesis',
      timestamp: new Date(Date.now() - 86400000).toISOString(), // 1 day ago
    },
  ]

  test.beforeEach(async ({ page }) => {
    // Setup: Mock authentication and stats
    await mockAuthMe(page, testData.user)
    await mockDashboardStats(page, mockStats)

    // Mock recent activity endpoint
    await mockApiRoute(page, '**/api/v1/documents/activity', mockRecentActivity)

    // Login and navigate to dashboard
    await mockLogin(page, testData.user.email)
  })

  test('should display all stat cards with correct values', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)

    // Verify stat cards visible
    const statsSection = page.locator('[data-testid="dashboard-stats"]')
    await expect(statsSection).toBeVisible()

    // Total documents
    const totalDocsCard = page.locator('[data-testid="stat-total-documents"]')
    await expect(totalDocsCard).toBeVisible()
    await expect(totalDocsCard).toContainText(mockStats.total_documents.toString())

    // Completed documents
    const completedCard = page.locator('[data-testid="stat-completed"]')
    await expect(completedCard).toBeVisible()
    await expect(completedCard).toContainText(mockStats.completed.toString())

    // In progress
    const inProgressCard = page.locator('[data-testid="stat-in-progress"]')
    await expect(inProgressCard).toBeVisible()
    await expect(inProgressCard).toContainText(mockStats.in_progress.toString())

    // Total spent
    const totalSpentCard = page.locator('[data-testid="stat-total-spent"]')
    await expect(totalSpentCard).toBeVisible()
    await expect(totalSpentCard).toContainText(`€${mockStats.total_spent.toFixed(2)}`)
  })

  test('should display recent activity list', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)

    // Verify recent activity section
    const activitySection = page.locator('[data-testid="recent-activity"]')
    await expect(activitySection).toBeVisible()

    // Verify activity items count
    const activityItems = page.locator('[data-testid^="activity-item-"]')
    await expect(activityItems).toHaveCount(mockRecentActivity.length)

    // Verify first activity item details
    const firstItem = page.locator('[data-testid="activity-item-1"]')
    await expect(firstItem).toContainText('AI Ethics Research')
    await expect(firstItem).toContainText(/completed/i)

    // Verify second activity item
    const secondItem = page.locator('[data-testid="activity-item-2"]')
    await expect(secondItem).toContainText('€25.00')
    await expect(secondItem).toContainText(/payment/i)
  })

  test('should show empty state when no documents exist', async ({ page }) => {
    // Mock empty stats
    await mockDashboardStats(page, {
      total_documents: 0,
      completed: 0,
      in_progress: 0,
      failed: 0,
      total_spent: 0,
    })

    await mockApiRoute(page, '**/api/v1/documents/activity', [])

    // Reload dashboard
    await page.reload()

    // Verify empty state displayed
    const emptyState = page.locator('[data-testid="empty-state"]')
    await expect(emptyState).toBeVisible()
    await expect(emptyState).toContainText(/no documents yet/i)

    // Verify "Create Document" CTA prominent
    const createButton = page.locator('button[data-testid="create-first-document-btn"]')
    await expect(createButton).toBeVisible()
  })

  test('should handle stats loading error gracefully', async ({ page }) => {
    // Mock stats endpoint error
    await mockApiRoute(
      page,
      '**/api/v1/documents/stats',
      { detail: 'Service unavailable' },
      503
    )

    // Reload dashboard
    await page.reload()

    // Should show error state
    const errorState = page.locator('[data-testid="stats-error"]')
    await expect(errorState).toBeVisible()
    await expect(errorState).toContainText(/unable to load stats/i)

    // Should show retry button
    const retryButton = page.locator('button[data-testid="retry-stats-btn"]')
    await expect(retryButton).toBeVisible()
  })
})
