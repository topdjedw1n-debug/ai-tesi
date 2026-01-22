/**
 * E2E Test: Magic Link Authentication Flow
 *
 * Tests complete authentication journey:
 * 1. User lands on /auth/login
 * 2. Enters email and requests magic link
 * 3. System sends email (mocked)
 * 4. User clicks magic link (simulated via token in URL)
 * 5. System verifies token and redirects to /dashboard
 * 6. Dashboard displays user info
 */

import { test, expect } from '@playwright/test'
import { mockApiRoute, mockAuthMe, testData } from './helpers'

test.describe('Magic Link Authentication', () => {
  test('should complete full authentication flow from login to dashboard', async ({ page }) => {
    // Step 1: Navigate to login page
    await page.goto('/auth/login')

    // Verify login page loaded
    await expect(page).toHaveTitle(/TesiGo/i)
    await expect(page.locator('h1')).toContainText(/sign in/i)

    // Step 2: User enters email
    const emailInput = page.locator('input[type="email"]')
    await expect(emailInput).toBeVisible()
    await emailInput.fill(testData.validEmail)

    // Step 3: Mock API response for magic link request
    await mockApiRoute(page, '**/api/v1/auth/magic-link', {
      message: 'Magic link sent to your email',
      email: testData.validEmail,
    })

    // Step 4: Click "Send Magic Link" button
    const sendButton = page.locator('button', { hasText: /send.*magic.*link/i })
    await sendButton.click()

    // Verify success message appears
    await expect(page.locator('text=check your email')).toBeVisible({ timeout: 5000 })

    // Step 5: Simulate clicking magic link (navigate to verify page with token)
    const mockToken = 'mock-token-123456'

    // Mock verify endpoint to return access/refresh tokens
    await mockApiRoute(page, '**/api/v1/auth/verify-magic-link', {
      access_token: 'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...',
      refresh_token: 'refresh_token_value',
      token_type: 'bearer',
    })

    // Mock /auth/me endpoint (returns user data after verification)
    await mockAuthMe(page, testData.user)

    // Navigate to verify page (simulates clicking link in email)
    await page.goto(`/auth/verify?token=${mockToken}`)

    // Step 6: System should redirect to dashboard after successful verification
    await page.waitForURL('**/dashboard', { timeout: 10000 })

    // Verify dashboard loaded
    await expect(page).toHaveURL(/\/dashboard/)

    // Verify user info displayed
    await expect(page.locator(`text=${testData.user.email}`)).toBeVisible()
  })

  test('should show error for invalid magic link token', async ({ page }) => {
    // Mock verify endpoint to return error
    await mockApiRoute(
      page,
      '**/api/v1/auth/verify-magic-link',
      { detail: 'Invalid or expired token' },
      400
    )

    // Navigate with invalid token
    await page.goto('/auth/verify?token=invalid-token')

    // Should show error message
    await expect(page.locator('text=/invalid.*token/i')).toBeVisible({ timeout: 5000 })

    // Should NOT redirect to dashboard
    await expect(page).not.toHaveURL(/\/dashboard/)
  })

  test('should enforce rate limiting on magic link requests', async ({ page }) => {
    await page.goto('/auth/login')

    const emailInput = page.locator('input[type="email"]')
    await emailInput.fill(testData.validEmail)

    // First request succeeds
    await mockApiRoute(page, '**/api/v1/auth/magic-link', {
      message: 'Magic link sent',
    })

    const sendButton = page.locator('button', { hasText: /send.*magic.*link/i })
    await sendButton.click()
    await expect(page.locator('text=check your email')).toBeVisible()

    // Mock rate limit error for subsequent request
    await mockApiRoute(
      page,
      '**/api/v1/auth/magic-link',
      { detail: 'Too many requests. Try again tomorrow.' },
      429
    )

    // Try to request again
    await page.reload()
    await emailInput.fill(testData.validEmail)
    await sendButton.click()

    // Should show rate limit error
    await expect(page.locator('text=/too many requests/i')).toBeVisible()
  })
})
