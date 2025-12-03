/**
 * E2E Test: Payment Checkout Flow
 * 
 * Tests payment journey:
 * 1. User has draft document (payment required)
 * 2. Views document detail page
 * 3. Sees payment calculation (pages × €0.50)
 * 4. Clicks "Pay & Generate"
 * 5. System creates Stripe checkout session
 * 6. Redirects to Stripe checkout page
 */

import { test, expect } from '@playwright/test'
import { mockLogin, mockAuthMe, mockApiRoute, testData } from './helpers'

test.describe('Payment Checkout Flow', () => {
  const draftDocument = {
    id: 101,
    title: 'Test Thesis',
    topic: 'AI in Healthcare',
    language: 'en',
    pages: 25,
    status: 'draft',
    user_id: testData.user.id,
    created_at: new Date().toISOString(),
  }
  
  test.beforeEach(async ({ page }) => {
    // Setup: Mock authentication
    await mockAuthMe(page, testData.user)
    await mockLogin(page, testData.user.email)
    
    // Mock document detail endpoint
    await mockApiRoute(page, `**/api/v1/documents/${draftDocument.id}`, draftDocument)
    
    // Navigate to document page
    await page.goto(`/dashboard/documents/${draftDocument.id}`)
  })
  
  test('should display correct payment calculation', async ({ page }) => {
    // Verify document title
    await expect(page.locator('h1')).toContainText(draftDocument.title)
    
    // Verify status = draft (payment required)
    await expect(page.locator('[data-testid="document-status"]')).toContainText(/draft/i)
    
    // Verify payment calculation displayed
    const pricePerPage = 0.50
    const totalPrice = draftDocument.pages * pricePerPage
    
    await expect(page.locator('[data-testid="price-calculation"]')).toContainText(
      `${draftDocument.pages} × €${pricePerPage.toFixed(2)}`
    )
    
    await expect(page.locator('[data-testid="total-price"]')).toContainText(
      `€${totalPrice.toFixed(2)}`
    )
  })
  
  test('should redirect to Stripe checkout on payment', async ({ page }) => {
    // Verify "Pay & Generate" button visible
    const payButton = page.locator('button[data-testid="pay-generate-btn"]')
    await expect(payButton).toBeVisible()
    await expect(payButton).toContainText(/pay.*generate/i)
    
    // Mock payment intent creation endpoint
    const mockCheckoutSession = {
      checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_mock123',
      session_id: 'cs_test_mock123',
      amount: 1250, // €12.50 in cents (25 pages × €0.50)
    }
    
    await mockApiRoute(
      page,
      `**/api/v1/payment/create-intent`,
      mockCheckoutSession,
      201
    )
    
    // Click pay button
    await payButton.click()
    
    // Wait for navigation to Stripe (mocked URL)
    // In real scenario, Stripe URL would load. In test, we just verify redirect attempt.
    await page.waitForURL('**/checkout.stripe.com/**', { timeout: 10000 })
    
    // Verify redirected to Stripe
    expect(page.url()).toContain('checkout.stripe.com')
  })
  
  test('should handle payment creation failure', async ({ page }) => {
    const payButton = page.locator('button[data-testid="pay-generate-btn"]')
    
    // Mock payment error
    await mockApiRoute(
      page,
      `**/api/v1/payment/create-intent`,
      { detail: 'Payment provider unavailable' },
      503
    )
    
    await payButton.click()
    
    // Should show error message
    await expect(page.locator('text=/payment.*unavailable/i')).toBeVisible({ timeout: 5000 })
    
    // Should remain on document page
    await expect(page).toHaveURL(`**/dashboard/documents/${draftDocument.id}`)
  })
  
  test('should disable pay button while processing', async ({ page }) => {
    const payButton = page.locator('button[data-testid="pay-generate-btn"]')
    
    // Mock slow payment response (to test loading state)
    await mockApiRoute(
      page,
      `**/api/v1/payment/create-intent`,
      { checkout_url: 'https://checkout.stripe.com/c/pay/cs_test_mock123' },
      201
    )
    
    // Click button
    await payButton.click()
    
    // Button should be disabled during processing
    await expect(payButton).toBeDisabled()
    
    // Loading indicator should appear
    await expect(page.locator('[data-testid="payment-loading"]')).toBeVisible()
  })
})
