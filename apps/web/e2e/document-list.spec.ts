/**
 * E2E Test: Document List & Filtering
 * 
 * Tests document list functionality:
 * 1. Dashboard shows document list/cards
 * 2. Each document displays: title, status, pages, date
 * 3. User can filter by status (all, draft, generating, completed, failed)
 * 4. User can sort (newest, oldest)
 * 5. Clicking document navigates to detail page
 * 6. Delete button shows confirmation and removes document
 */

import { test, expect } from '@playwright/test'
import { mockLogin, mockAuthMe, mockApiRoute, mockDocumentsList, testData } from './helpers'

test.describe('Document List & Filtering', () => {
  const mockDocuments = [
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
      created_at: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
    },
    {
      id: 3,
      title: 'Quantum Computing Paper',
      status: 'draft',
      pages: 30,
      language: 'en',
      created_at: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
    },
    {
      id: 4,
      title: 'Failed Generation Test',
      status: 'failed',
      pages: 15,
      language: 'de',
      created_at: new Date(Date.now() - 172800000).toISOString(), // 2 days ago
    },
  ]
  
  test.beforeEach(async ({ page }) => {
    // Setup: Mock authentication and documents list
    await mockAuthMe(page, testData.user)
    await mockDocumentsList(page, mockDocuments)
    
    // Login and navigate to dashboard
    await mockLogin(page, testData.user.email)
  })
  
  test('should display document list with all documents', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)
    
    // Verify documents section visible
    const documentsSection = page.locator('[data-testid="documents-list"]')
    await expect(documentsSection).toBeVisible()
    
    // Verify all documents displayed
    const documentCards = page.locator('[data-testid^="document-card-"]')
    await expect(documentCards).toHaveCount(mockDocuments.length)
    
    // Verify first document details
    const firstDoc = page.locator('[data-testid="document-card-1"]')
    await expect(firstDoc).toContainText('AI Ethics Research')
    await expect(firstDoc).toContainText('completed')
    await expect(firstDoc).toContainText('25') // pages
  })
  
  test('should filter documents by status', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)
    
    // Click "Completed" filter
    const completedFilter = page.locator('[data-testid="filter-completed"]')
    await completedFilter.click()
    
    // Should show only completed documents
    const visibleDocs = page.locator('[data-testid^="document-card-"]')
    await expect(visibleDocs).toHaveCount(1) // Only 1 completed
    await expect(visibleDocs.first()).toContainText('AI Ethics Research')
    
    // Click "Generating" filter
    const generatingFilter = page.locator('[data-testid="filter-generating"]')
    await generatingFilter.click()
    
    // Should show only generating documents
    await expect(visibleDocs).toHaveCount(1)
    await expect(visibleDocs.first()).toContainText('Machine Learning Thesis')
    
    // Click "All" to reset
    const allFilter = page.locator('[data-testid="filter-all"]')
    await allFilter.click()
    
    // Should show all documents again
    await expect(visibleDocs).toHaveCount(mockDocuments.length)
  })
  
  test('should sort documents by date', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)
    
    // Default sort: Newest first
    const documentCards = page.locator('[data-testid^="document-card-"]')
    
    // First document should be "Machine Learning Thesis" (2 hours ago)
    await expect(documentCards.nth(0)).toContainText('Machine Learning Thesis')
    
    // Click "Oldest" sort
    const oldestSort = page.locator('[data-testid="sort-oldest"]')
    await oldestSort.click()
    
    // First document should now be "Failed Generation Test" (2 days ago)
    await expect(documentCards.nth(0)).toContainText('Failed Generation Test')
  })
  
  test('should navigate to document detail on click', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)
    
    // Mock document detail endpoint
    await mockApiRoute(page, `**/api/v1/documents/${mockDocuments[0].id}`, mockDocuments[0])
    
    // Click on first document card
    const firstDoc = page.locator('[data-testid="document-card-1"]')
    await firstDoc.click()
    
    // Should navigate to document detail page
    await page.waitForURL(`**/dashboard/documents/${mockDocuments[0].id}`, { timeout: 10000 })
    
    // Verify document detail page loaded
    await expect(page.locator('h1')).toContainText(mockDocuments[0].title)
  })
  
  test('should delete document with confirmation', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)
    
    // Find delete button for first document
    const deleteButton = page.locator('[data-testid="delete-document-1"]')
    await deleteButton.click()
    
    // Confirmation dialog should appear
    const confirmDialog = page.locator('[data-testid="delete-confirmation-dialog"]')
    await expect(confirmDialog).toBeVisible()
    await expect(confirmDialog).toContainText(/are you sure/i)
    
    // Mock delete endpoint
    await mockApiRoute(page, `**/api/v1/documents/${mockDocuments[0].id}`, {}, 204)
    
    // Mock updated documents list (without deleted document)
    const updatedDocs = mockDocuments.filter(doc => doc.id !== mockDocuments[0].id)
    await mockApiRoute(page, '**/api/v1/documents', updatedDocs)
    
    // Confirm deletion
    const confirmButton = page.locator('[data-testid="confirm-delete-btn"]')
    await confirmButton.click()
    
    // Document should disappear from list
    const documentCards = page.locator('[data-testid^="document-card-"]')
    await expect(documentCards).toHaveCount(updatedDocs.length)
    
    // Deleted document should not be in list
    await expect(page.locator('[data-testid="document-card-1"]')).not.toBeVisible()
  })
  
  test('should cancel deletion on dialog cancel', async ({ page }) => {
    await expect(page).toHaveURL(/\/dashboard/)
    
    // Click delete button
    const deleteButton = page.locator('[data-testid="delete-document-1"]')
    await deleteButton.click()
    
    // Confirmation dialog appears
    const confirmDialog = page.locator('[data-testid="delete-confirmation-dialog"]')
    await expect(confirmDialog).toBeVisible()
    
    // Click cancel
    const cancelButton = page.locator('[data-testid="cancel-delete-btn"]')
    await cancelButton.click()
    
    // Dialog should close
    await expect(confirmDialog).not.toBeVisible()
    
    // Document should still be in list
    const documentCards = page.locator('[data-testid^="document-card-"]')
    await expect(documentCards).toHaveCount(mockDocuments.length)
    await expect(page.locator('[data-testid="document-card-1"]')).toBeVisible()
  })
})
