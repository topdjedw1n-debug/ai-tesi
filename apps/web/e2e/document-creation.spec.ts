/**
 * E2E Test: Document Creation Flow
 *
 * Tests complete document creation journey:
 * 1. User authenticated and on dashboard
 * 2. Clicks "Create Document" or fills form on dashboard
 * 3. Enters title, topic, language, pages
 * 4. Submits form
 * 5. System creates document
 * 6. Redirects to document detail page
 * 7. Shows payment required state
 */

import { test, expect } from '@playwright/test'
import { mockLogin, mockAuthMe, mockApiRoute, fillDocumentForm, testData } from './helpers'

test.describe('Document Creation Flow', () => {
  test.beforeEach(async ({ page }) => {
    // Setup: Mock authentication
    await mockAuthMe(page, testData.user)
    await mockLogin(page, testData.user.email)
  })

  test('should create document from dashboard form', async ({ page }) => {
    // User is on dashboard (from beforeEach)
    await expect(page).toHaveURL(/\/dashboard/)

    // Verify "Create Document" form/section visible
    const createSection = page.locator('[data-testid="create-document-section"]')
    await expect(createSection).toBeVisible()

    // Fill document form
    await fillDocumentForm(page, {
      title: testData.document.title,
      topic: testData.document.topic,
      language: testData.document.language,
      pages: testData.document.pages,
    })

    // Mock API response for document creation
    const createdDocument = {
      id: 123,
      ...testData.document,
      user_id: testData.user.id,
      status: 'draft',
      created_at: new Date().toISOString(),
    }

    await mockApiRoute(page, '**/api/v1/documents', createdDocument, 201)

    // Submit form
    const createButton = page.locator('button[data-testid="create-document-btn"]')
    await createButton.click()

    // Should redirect to document detail page
    await page.waitForURL(`**/dashboard/documents/${createdDocument.id}`, { timeout: 10000 })

    // Verify document detail page loaded
    await expect(page.locator('h1')).toContainText(testData.document.title)

    // Verify status badge shows "Draft"
    await expect(page.locator('[data-testid="document-status"]')).toContainText(/draft/i)

    // Verify payment required section visible (since status = draft)
    await expect(page.locator('[data-testid="payment-required-section"]')).toBeVisible()
  })

  test('should validate minimum page count (3 pages)', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)

    // Try to create document with 2 pages (invalid)
    await fillDocumentForm(page, {
      title: 'Invalid Document',
      topic: 'Test topic',
      pages: 2, // Less than minimum (3)
    })

    const createButton = page.locator('button[data-testid="create-document-btn"]')
    await createButton.click()

    // Should show validation error
    await expect(page.locator('text=/minimum.*3.*pages/i')).toBeVisible()

    // Should NOT make API call (form validation prevents it)
    await expect(page).toHaveURL(/\/dashboard/) // Still on dashboard
  })

  test('should handle document creation failure gracefully', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)

    await fillDocumentForm(page, {
      title: testData.document.title,
      topic: testData.document.topic,
    })

    // Mock API error response
    await mockApiRoute(
      page,
      '**/api/v1/documents',
      { detail: 'Server error: Unable to create document' },
      500
    )

    const createButton = page.locator('button[data-testid="create-document-btn"]')
    await createButton.click()

    // Should show error message
    await expect(page.locator('text=/unable to create/i')).toBeVisible({ timeout: 5000 })

    // Should remain on dashboard
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('should update document count after creation', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)

    // Mock stats endpoint to return initial count
    await mockApiRoute(page, '**/api/v1/documents/stats', {
      total_documents: 5,
      completed: 3,
      in_progress: 1,
    })

    // Check initial stats
    await expect(page.locator('[data-testid="total-documents-count"]')).toContainText('5')

    // Create new document
    await fillDocumentForm(page, testData.document)

    const createdDocument = {
      id: 124,
      ...testData.document,
      status: 'draft',
    }

    await mockApiRoute(page, '**/api/v1/documents', createdDocument, 201)

    // Mock updated stats (count increased)
    await mockApiRoute(page, '**/api/v1/documents/stats', {
      total_documents: 6, // Increased
      completed: 3,
      in_progress: 1,
    })

    const createButton = page.locator('button[data-testid="create-document-btn"]')
    await createButton.click()

    // Wait for redirect
    await page.waitForURL(`**/dashboard/documents/${createdDocument.id}`)

    // Navigate back to dashboard
    await page.goto('/dashboard')

    // Verify updated count
    await expect(page.locator('[data-testid="total-documents-count"]')).toContainText('6')
  })
})
