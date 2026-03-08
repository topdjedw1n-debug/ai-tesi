/**
 * Pre-prod Manual UI Smoke Test – Strict Mode
 * 
 * Uses REAL API calls (no mocks). Tests all critical user and admin flows
 * against the running Docker stack.
 * 
 * Run: cd apps/web && unset CI && npx playwright test e2e/smoke-preprod.spec.ts --reporter=list --project=chromium
 */

import { test, expect, Page } from '@playwright/test'

const BASE_URL = 'http://localhost:3000'
const API_URL = 'http://localhost:8000'

const ADMIN_EMAIL = 'admin@tesigo.com'
const ADMIN_PASSWORD = 'admin123'
const TEST_USER_EMAIL = 'testuser@tesigo.com'

// ────────────────────────────────────────────────
// Shared state (fetched once per test run)
// ────────────────────────────────────────────────
let USER_TOKEN: string = ''
let ADMIN_TOKEN: string = ''
let ADMIN_USER_DATA: object = {}

// ────────────────────────────────────────────────
// API helpers (Node.js fetch, not browser)
// ────────────────────────────────────────────────
async function fetchAdminToken(): Promise<{ token: string; user: object }> {
  const res = await fetch(`${API_URL}/api/v1/auth/admin-login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: ADMIN_EMAIL, password: ADMIN_PASSWORD }),
  })
  if (!res.ok) throw new Error(`Admin login failed: ${res.status}`)
  const data = await res.json() as { access_token: string; user: object }
  return { token: data.access_token, user: data.user }
}

async function fetchUserToken(): Promise<string> {
  // 1. Request magic link
  const mlRes = await fetch(`${API_URL}/api/v1/auth/magic-link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ email: TEST_USER_EMAIL }),
  })
  if (!mlRes.ok) {
    const err = await mlRes.text()
    throw new Error(`Magic link request failed ${mlRes.status}: ${err}`)
  }
  const mlData = await mlRes.json() as { magic_link: string }
  const magicLink = mlData.magic_link

  // Extract token from URL
  let token: string
  try {
    const url = new URL(magicLink)
    token = url.searchParams.get('token') || ''
  } catch {
    // If not a full URL, try treating as path
    const match = magicLink.match(/token=([^&]+)/)
    token = match ? match[1] : magicLink
  }
  if (!token) throw new Error('No token in magic link: ' + magicLink)

  // 2. Verify token
  const verifyRes = await fetch(`${API_URL}/api/v1/auth/verify-magic-link`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ token }),
  })
  if (!verifyRes.ok) {
    const err = await verifyRes.text()
    throw new Error(`Magic link verify failed ${verifyRes.status}: ${err}`)
  }
  const verifyData = await verifyRes.json() as { access_token: string }
  return verifyData.access_token
}

// ────────────────────────────────────────────────
// Setup: fetch all tokens ONCE before tests
// ────────────────────────────────────────────────
test.beforeAll(async () => {
  console.log('\n' + '='.repeat(60))
  console.log('PRE-PROD SMOKE TEST SETUP')
  console.log('='.repeat(60))

  // Admin token
  try {
    const { token, user } = await fetchAdminToken()
    ADMIN_TOKEN = token
    ADMIN_USER_DATA = user
    console.log('✅ Admin token acquired')
  } catch (e: any) {
    console.log(`❌ Admin token FAILED: ${e.message}`)
    console.log('   Admin scenarios will be BLOCKED')
  }

  // User token
  try {
    USER_TOKEN = await fetchUserToken()
    console.log('✅ User token acquired')
  } catch (e: any) {
    console.log(`❌ User token FAILED: ${e.message}`)
    console.log('   User scenarios will be BLOCKED')
  }

  console.log('='.repeat(60) + '\n')
})

// ────────────────────────────────────────────────
// Helper: inject user session into browser
// ────────────────────────name──────────────────────
async function injectUserSession(page: Page) {
  if (!USER_TOKEN) throw new Error('USER_TOKEN not available')
  await page.addInitScript((token: string) => {
    localStorage.setItem('auth_token', token)
  }, USER_TOKEN)
}

async function injectAdminSession(page: Page) {
  if (!ADMIN_TOKEN) throw new Error('ADMIN_TOKEN not available')
  await page.addInitScript((data: { token: string; user: object }) => {
    localStorage.setItem('auth_token', data.token)
    localStorage.setItem('admin_user', JSON.stringify(data.user))
    localStorage.setItem('is_admin', 'true')
  }, { token: ADMIN_TOKEN, user: ADMIN_USER_DATA })
}

// ────────────────────────────────────────────────
// Network monitor helper
// ────────────────────────────────────────────────
function attachNetworkMonitor(page: Page) {
  const consoleErrors: string[] = []
  const failedRequests: Array<{ url: string; status: number }> = []

  page.on('console', (msg) => {
    if (msg.type() === 'error') consoleErrors.push(msg.text())
  })
  page.on('response', (response) => {
    const url = response.url()
    const status = response.status()
    // Only track localhost requests with error status
    if ((url.includes('localhost:8000') || url.includes('localhost:3000/api')) && status >= 400) {
      failedRequests.push({ url, status })
    }
  })

  return { consoleErrors, failedRequests }
}

// ────────────────────────────────────────────────
// S1: Landing Page
// ────────────────────────────────────────────────
test('S1 – Landing page loads', async ({ page }) => {
  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await page.goto(BASE_URL, { waitUntil: 'networkidle' })
  const title = await page.title()
  const url = page.url()
  const bodyText = await page.textContent('body') || ''

  console.log(`\nS1 – Landing Page`)
  console.log(`  URL: ${url}`)
  console.log(`  Title: ${title}`)
  console.log(`  Body length: ${bodyText.trim().length}`)
  console.log(`  Console errors: ${consoleErrors.length}`)
  consoleErrors.forEach(e => console.log(`    ❌ Console: ${e}`))
  console.log(`  Failed HTTP: ${failedRequests.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)

  const hasContent = bodyText.trim().length > 100
  const noHard404 = !bodyText.includes('404') || bodyText.includes('TesiGo')

  const result = hasContent && noHard404 ? 'PASS' : 'FAIL'
  console.log(`  → RESULT: ${result}`)
  if (consoleErrors.length > 0) console.log(`  → Console errors: P1 defect`)
  expect(hasContent).toBe(true)
})

// ────────────────────────────────────────────────
// S2: Auth Login Page UI
// ────────────────────────────────────────────────
test('S2 – Auth login page UI', async ({ page }) => {
  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await page.goto(`${BASE_URL}/auth/login`, { waitUntil: 'networkidle' })
  const url = page.url()
  const bodyText = await page.textContent('body') || ''

  // Check for email input (magic link form)
  const emailInput = page.locator('input[type="email"]').first()
  const hasEmailInput = await emailInput.isVisible().catch(() => false)

  console.log(`\nS2 – Auth Login Page`)
  console.log(`  URL: ${url}`)
  console.log(`  Body length: ${bodyText.trim().length}`)
  console.log(`  Email input visible: ${hasEmailInput}`)
  console.log(`  Console errors: ${consoleErrors.length}`)
  consoleErrors.forEach(e => console.log(`    ❌ ${e}`))
  console.log(`  Failed HTTP: ${failedRequests.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)

  if (!hasEmailInput) {
    console.log(`  → RESULT: FAIL – no email input on login page`)
    console.log(`  → DEFECT P0: Magic link login form not found`)
  } else {
    console.log(`  → RESULT: PASS`)
  }
})

// ────────────────────────────────────────────────
// S3: Dashboard Load (with real user token)
// ────────────────────────────────────────────────
test('S3 – Dashboard loads with real user token', async ({ page }) => {
  if (!USER_TOKEN) {
    console.log(`\nS3 – BLOCKED: No user token available`)
    test.skip()
    return
  }

  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await injectUserSession(page)
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle' })
  const url = page.url()
  const bodyText = await page.textContent('body') || ''

  const isOnDashboard = url.includes('/dashboard') && !url.includes('/login')
  const hasContent = bodyText.trim().length > 100
  const critErrors = failedRequests.filter(r => r.status >= 500)
  const authErrors = failedRequests.filter(r => r.status === 401)

  console.log(`\nS3 – Dashboard`)
  console.log(`  URL: ${url}`)
  console.log(`  On dashboard: ${isOnDashboard}`)
  console.log(`  Body length: ${bodyText.trim().length}`)
  console.log(`  Console errors: ${consoleErrors.filter(e => !e.includes('favicon')).length}`)
  consoleErrors.filter(e => !e.includes('favicon')).forEach(e => console.log(`    ❌ ${e}`))
  console.log(`  Auth errors (401): ${authErrors.map(r => r.url).join(', ') || 'none'}`)
  console.log(`  Server errors (5xx): ${critErrors.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)

  if (!isOnDashboard) {
    console.log(`  → RESULT: FAIL – redirected to ${url}`)
    console.log(`  → DEFECT P0: Dashboard redirect with valid token`)
  } else if (!hasContent) {
    console.log(`  → RESULT: FAIL – blank screen`)
    console.log(`  → DEFECT P0: Dashboard blank screen`)
  } else if (critErrors.length > 0) {
    console.log(`  → RESULT: FAIL – server errors`)
    console.log(`  → DEFECT P0: 5xx errors on dashboard`)
  } else {
    console.log(`  → RESULT: PASS`)
  }
})

// ────────────────────────────────────────────────
// S4: Create Document Form
// ────────────────────────────────────────────────
test('S4 – Create document form', async ({ page }) => {
  if (!USER_TOKEN) {
    console.log(`\nS4 – BLOCKED: No user token available`)
    test.skip()
    return
  }

  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await injectUserSession(page)
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle' })
  const dashUrl = page.url()

  console.log(`\nS4 – Create Document Form`)
  console.log(`  Dashboard URL: ${dashUrl}`)

  if (!dashUrl.includes('/dashboard')) {
    console.log(`  → BLOCKED: Not on dashboard (${dashUrl}), cannot test create form`)
    return
  }

  // Look for create/generate button
  const createSelectors = [
    'a[href*="/generate"]', 'a[href*="/document/new"]', 'a[href*="/create"]',
    'button:has-text("Generate")', 'button:has-text("Create")', 'button:has-text("New")',
    'text=Generate Document', 'text=New Document', 'text=Create Document',
  ]

  let createUrl: string | null = null
  for (const sel of createSelectors) {
    const el = page.locator(sel).first()
    if (await el.isVisible().catch(() => false)) {
      const href = await el.getAttribute('href').catch(() => null)
      console.log(`  Found create button: ${sel} (href: ${href || 'button'})`)
      if (href) {
        createUrl = href.startsWith('http') ? href : `${BASE_URL}${href}`
      } else {
        await el.click()
        await page.waitForLoadState('networkidle')
        createUrl = page.url()
      }
      break
    }
  }

  // Also try direct URLs
  if (!createUrl) {
    const candidateUrls = [
      `${BASE_URL}/generate`,
      `${BASE_URL}/document/new`,
      `${BASE_URL}/documents/new`,
      `${BASE_URL}/dashboard/create`,
    ]
    for (const u of candidateUrls) {
      await page.goto(u, { waitUntil: 'networkidle' })
      const text = await page.textContent('body') || ''
      const hasTitleInput = await page.locator('input').count() > 0
      if (!page.url().includes('/login') && text.length > 100) {
        createUrl = page.url()
        console.log(`  Found create form at: ${createUrl}`)
        break
      }
    }
  }

  if (!createUrl) {
    console.log(`  → RESULT: BLOCKED – no create document path found`)
    console.log(`  → DEFECT P1: No document creation entry point`)
    return
  }

  if (!page.url().includes(createUrl.replace(BASE_URL, ''))) {
    await page.goto(createUrl, { waitUntil: 'networkidle' })
  }

  const formUrl = page.url()
  const bodyText = await page.textContent('body') || ''
  const inputCount = await page.locator('input, textarea, select').count()

  console.log(`  Form URL: ${formUrl}`)
  console.log(`  Input fields count: ${inputCount}`)
  console.log(`  Body length: ${bodyText.trim().length}`)

  const hasForm = inputCount > 0 && !formUrl.includes('/login')

  if (!hasForm) {
    console.log(`  → RESULT: FAIL – no form inputs at ${formUrl}`)
    console.log(`  → DEFECT P1: Document creation form has no inputs`)
    return
  }

  // Try to fill form
  const titleInput = page.locator('input[name*="title"], input[placeholder*="itle"], input[placeholder*="назв"]').first()
  if (await titleInput.isVisible().catch(() => false)) {
    await titleInput.fill('Smoke Test Thesis')
  }

  const pagesInput = page.locator('input[type="number"], input[name*="pages"]').first()
  if (await pagesInput.isVisible().catch(() => false)) {
    await pagesInput.fill('3')
  }

  // Submit
  const submitBtn = page.locator('button[type="submit"]').first()
  if (await submitBtn.isVisible().catch(() => false)) {
    await submitBtn.click()
    await page.waitForLoadState('networkidle')
    const postSubmitUrl = page.url()
    const postErrors = failedRequests.filter(r => r.status >= 400 && (r.url.includes('generate') || r.url.includes('document')))

    console.log(`  After submit URL: ${postSubmitUrl}`)
    console.log(`  Post-submit API errors: ${postErrors.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)

    if (postErrors.some(r => r.status >= 500)) {
      console.log(`  → RESULT: FAIL – server error on submit`)
      console.log(`  → DEFECT P0: Document generation returns 5xx`)
    } else if (postErrors.some(r => r.status === 422)) {
      console.log(`  → RESULT: PARTIAL PASS – 422 validation (form filled with minimal data)`)
    } else if (postErrors.length > 0) {
      console.log(`  → RESULT: FAIL – ${postErrors[0].status} on submit`)
    } else {
      console.log(`  → RESULT: PASS – form submitted successfully`)
    }
  } else {
    console.log(`  → RESULT: PARTIAL PASS – form visible but no submit button found`)
  }

  consoleErrors.filter(e => !e.includes('favicon') && !e.includes('ResizeObserver')).forEach(e => console.log(`    ❌ ${e}`))
})

// ────────────────────────────────────────────────
// S5: Payment History
// ────────────────────────────────────────────────
test('S5 – Payment history page', async ({ page }) => {
  if (!USER_TOKEN) {
    console.log(`\nS5 – BLOCKED: No user token available`)
    test.skip()
    return
  }

  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await injectUserSession(page)

  const candidates = [
    `${BASE_URL}/payment/history`,
    `${BASE_URL}/dashboard/payments`,
    `${BASE_URL}/payments`,
  ]

  console.log(`\nS5 – Payment History`)
  let result = 'BLOCKED'
  let loadedUrl = ''

  for (const u of candidates) {
    await page.goto(u, { waitUntil: 'networkidle' })
    const url = page.url()
    const body = await page.textContent('body') || ''
    const isLoginPage = url.includes('/login') || url.includes('/auth')
    const isBlank = body.trim().length < 100
    const is404 = body.toLowerCase().includes('404') && !body.includes('TesiGo')

    console.log(`  Tried ${u} → ${url} (blank: ${isBlank}, login: ${isLoginPage}, 404: ${is404})`)

    if (!isLoginPage && !isBlank && !is404) {
      result = 'PASS'
      loadedUrl = url
      break
    }
  }

  const apiErrors = failedRequests.filter(r => r.url.includes('payment') && r.status >= 400)
  console.log(`  Payment API errors: ${apiErrors.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)

  if (apiErrors.some(r => r.status >= 500)) {
    result = 'FAIL'
    console.log(`  → DEFECT P0: Payment history API 5xx`)
  } else if (apiErrors.some(r => r.status === 404)) {
    result = 'FAIL'
    console.log(`  → DEFECT P1: Payment history endpoint not found (404)`)
  } else if (apiErrors.some(r => r.status === 405)) {
    result = 'FAIL'
    console.log(`  → DEFECT P0: Payment history endpoint method not allowed (405)`)
  }

  console.log(`  → RESULT: ${result}${loadedUrl ? ' at ' + loadedUrl : ''}`)
  consoleErrors.filter(e => !e.includes('favicon')).forEach(e => console.log(`    ❌ ${e}`))
})

// ────────────────────────────────────────────────
// S6: Refund List
// ────────────────────────────────────────────────
test('S6 – Refund list page', async ({ page }) => {
  if (!USER_TOKEN) {
    console.log(`\nS6 – BLOCKED: No user token available`)
    test.skip()
    return
  }

  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await injectUserSession(page)
  await page.goto(`${BASE_URL}/payment/refunds`, { waitUntil: 'networkidle' })
  const url = page.url()
  const body = await page.textContent('body') || ''

  const isLoginPage = url.includes('/login') || url.includes('/auth')
  const isBlank = body.trim().length < 100
  const apiErrors = failedRequests.filter(r => r.url.includes('refund') && r.status >= 400)

  console.log(`\nS6 – Refund List`)
  console.log(`  URL: ${url}`)
  console.log(`  Body length: ${body.trim().length}`)
  console.log(`  Login redirect: ${isLoginPage}`)
  console.log(`  Refund API errors: ${apiErrors.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)

  let result = 'PASS'
  if (isLoginPage) { result = 'FAIL'; console.log(`  → DEFECT P0: Redirected to login`) }
  else if (isBlank) { result = 'FAIL'; console.log(`  → DEFECT P0: Blank screen`) }
  else if (apiErrors.some(r => r.status === 404)) { result = 'FAIL'; console.log(`  → DEFECT P1: Refunds endpoint 404`) }
  else if (apiErrors.some(r => r.status === 405)) { result = 'FAIL'; console.log(`  → DEFECT P0: Refunds endpoint 405 Method Not Allowed`) }
  else if (apiErrors.some(r => r.status >= 500)) { result = 'FAIL'; console.log(`  → DEFECT P0: Refunds endpoint 5xx`) }

  console.log(`  → RESULT: ${result}`)
  consoleErrors.filter(e => !e.includes('favicon')).forEach(e => console.log(`    ❌ ${e}`))
})

// ────────────────────────────────────────────────
// S7: Refund Detail
// ────────────────────────────────────────────────
test('S7 – Refund detail (with empty state check)', async ({ page }) => {
  if (!USER_TOKEN) {
    console.log(`\nS7 – BLOCKED: No user token`)
    test.skip()
    return
  }

  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  // Check refunds via direct API
  const refundsRes = await fetch(`${API_URL}/api/v1/refunds`, {
    headers: { 'Authorization': `Bearer ${USER_TOKEN}` }
  })
  const refundStatus = refundsRes.status
  const refundsData: any = await refundsRes.json().catch(() => null)
  const refundList = Array.isArray(refundsData) ? refundsData : (refundsData?.items || refundsData?.data || [])

  console.log(`\nS7 – Refund Detail`)
  console.log(`  Refunds API status: ${refundStatus}`)
  console.log(`  Refunds count: ${refundList.length}`)

  if (refundStatus !== 200) {
    console.log(`  → DEFECT P1: GET /api/v1/refunds returns ${refundStatus}`)
    console.log(`  → RESULT: FAIL`)
    return
  }

  if (refundList.length === 0) {
    // Test empty state
    await injectUserSession(page)
    await page.goto(`${BASE_URL}/payment/refunds`, { waitUntil: 'networkidle' })
    const url = page.url()
    const body = await page.textContent('body') || ''
    const isLoginPage = url.includes('/login')
    const isBlank = body.trim().length < 100

    console.log(`  Empty state at ${url}: blank=${isBlank}, login=${isLoginPage}`)
    console.log(`  → RESULT: ${!isBlank && !isLoginPage ? 'PASS (empty state shown)' : 'FAIL (blank or login redirect)'}`)
    console.log(`  → NOTE: No refunds to test detail view – empty state verified`)
    return
  }

  // Test detail page with first refund
  await injectUserSession(page)
  await page.goto(`${BASE_URL}/payment/refunds/${refundList[0].id}`, { waitUntil: 'networkidle' })
  const url = page.url()
  const body = await page.textContent('body') || ''
  const apiErrors = failedRequests.filter(r => r.url.includes('refund') && r.status >= 400)

  console.log(`  Detail URL: ${url}`)
  console.log(`  Body length: ${body.trim().length}`)
  console.log(`  API errors: ${apiErrors.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)
  console.log(`  → RESULT: ${body.trim().length > 100 && !url.includes('/login') ? 'PASS' : 'FAIL'}`)
})

// ────────────────────────────────────────────────
// S8: User Logout
// ────────────────────────────────────────────────
test('S8 – User logout', async ({ page }) => {
  if (!USER_TOKEN) {
    console.log(`\nS8 – BLOCKED: No user token`)
    test.skip()
    return
  }

  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await injectUserSession(page)
  await page.goto(`${BASE_URL}/dashboard`, { waitUntil: 'networkidle' })
  const dashUrl = page.url()

  console.log(`\nS8 – User Logout`)
  console.log(`  Dashboard URL: ${dashUrl}`)

  if (!dashUrl.includes('/dashboard')) {
    console.log(`  → BLOCKED: Not on dashboard, cannot test logout`)
    return
  }

  // Look for logout
  const logoutSelectors = [
    'button:has-text("Logout")', 'button:has-text("Sign out")', 'button:has-text("Log out")',
    'a:has-text("Logout")', 'a:has-text("Sign out")',
    '[data-testid="logout-btn"]', 'text=Вийти', 'text=Logout',
  ]

  let logoutFound = false
  for (const sel of logoutSelectors) {
    const el = page.locator(sel).first()
    if (await el.isVisible().catch(() => false)) {
      console.log(`  Found logout: ${sel}`)
      await el.click()
      await page.waitForLoadState('networkidle')
      logoutFound = true
      break
    }
  }

  if (!logoutFound) {
    // Try opening user menu first
    const menuSelectors = ['[aria-label*="user"]', '[aria-label*="menu"]', '[aria-label*="account"]',
      'button:has-text("testuser")', 'button:has-text("@")', '.user-menu', '[data-testid="user-menu"]']
    for (const sel of menuSelectors) {
      const el = page.locator(sel).first()
      if (await el.isVisible().catch(() => false)) {
        await el.click()
        await page.waitForTimeout(800)
        for (const lsel of logoutSelectors) {
          const lel = page.locator(lsel).first()
          if (await lel.isVisible().catch(() => false)) {
            await lel.click()
            await page.waitForLoadState('networkidle')
            logoutFound = true
            break
          }
        }
        break
      }
    }
  }

  if (!logoutFound) {
    console.log(`  → RESULT: BLOCKED – no logout button found`)
    console.log(`  → DEFECT P1: No logout button visible on dashboard`)
    return
  }

  const afterUrl = page.url()
  const redirectedToAuth = afterUrl.includes('/login') || afterUrl.includes('/auth') || afterUrl === `${BASE_URL}/` || afterUrl === BASE_URL
  console.log(`  After logout: ${afterUrl}`)
  console.log(`  → RESULT: ${redirectedToAuth ? 'PASS' : 'FAIL – unexpected redirect to ' + afterUrl}`)

  if (!redirectedToAuth) {
    console.log(`  → DEFECT P1: Logout does not redirect to auth page`)
  }
})

// ────────────────────────────────────────────────
// S9: Admin Login via UI Form
// ────────────────────────────────────────────────
test('S9 – Admin login via UI form', async ({ page }) => {
  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await page.goto(`${BASE_URL}/admin/login`, { waitUntil: 'networkidle' })
  const url = page.url()
  const bodyText = await page.textContent('body') || ''

  console.log(`\nS9 – Admin Login (UI Form)`)
  console.log(`  URL: ${url}`)
  console.log(`  Body length: ${bodyText.trim().length}`)

  const emailInput = page.locator('input[type="email"], input[name="email"]').first()
  const passwordInput = page.locator('input[type="password"], input[name="password"]').first()
  const hasForm = await emailInput.isVisible().catch(() => false) && await passwordInput.isVisible().catch(() => false)

  if (!hasForm) {
    console.log(`  → RESULT: FAIL – no login form at /admin/login`)
    console.log(`  → DEFECT P0: Admin login form missing`)
    return
  }

  await emailInput.fill(ADMIN_EMAIL)
  await passwordInput.fill(ADMIN_PASSWORD)

  const submitBtn = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Login")').first()
  await submitBtn.click()
  // Wait up to 5s for navigation to admin dashboard (POST + redirect takes 2-3s)
  await page.waitForTimeout(4000)

  const afterUrl = page.url()
  const apiErrors = failedRequests.filter(r => r.url.includes('admin') && r.status >= 400)

  console.log(`  After login URL: ${afterUrl}`)
  console.log(`  API errors: ${apiErrors.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)

  const onAdminDashboard = afterUrl.includes('/admin') && !afterUrl.includes('/login')
  if (!onAdminDashboard) {
    console.log(`  → RESULT: FAIL – expected /admin/dashboard, got ${afterUrl}`)
    console.log(`  → DEFECT P0: Admin login UI form does not redirect to dashboard`)
  } else if (apiErrors.some(r => r.status >= 400)) {
    console.log(`  → RESULT: FAIL – API errors during admin login`)
  } else {
    console.log(`  → RESULT: PASS`)
  }
})

// ────────────────────────────────────────────────
// S10: Admin Dashboard Stats
// ────────────────────────────────────────────────
test('S10 – Admin dashboard with injected token', async ({ page }) => {
  if (!ADMIN_TOKEN) {
    console.log(`\nS10 – BLOCKED: No admin token`)
    test.skip()
    return
  }

  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await injectAdminSession(page)
  await page.goto(`${BASE_URL}/admin/dashboard`, { waitUntil: 'networkidle' })
  const url = page.url()
  const body = await page.textContent('body') || ''

  const isLogin = url.includes('/login')
  const isBlank = body.trim().length < 100
  const apiErrors = failedRequests.filter(r => r.status >= 400)
  const statErrors = failedRequests.filter(r => r.url.includes('stats') && r.status >= 400)

  console.log(`\nS10 – Admin Dashboard`)
  console.log(`  URL: ${url}`)
  console.log(`  Body length: ${body.trim().length}`)
  console.log(`  Login redirect: ${isLogin}`)
  console.log(`  All 4xx/5xx: ${apiErrors.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)
  console.log(`  Stats API errors: ${statErrors.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)
  consoleErrors.filter(e => !e.includes('favicon')).slice(0, 3).forEach(e => console.log(`    ❌ ${e}`))

  if (isLogin) {
    console.log(`  → RESULT: FAIL – admin dashboard redirects to login`)
    console.log(`  → DEFECT P0: Admin session localStorage injection fails to keep admin logged in`)
  } else if (isBlank) {
    console.log(`  → RESULT: FAIL – blank screen`)
    console.log(`  → DEFECT P0: Admin dashboard blank screen`)
  } else if (statErrors.some(r => r.status >= 500)) {
    console.log(`  → RESULT: FAIL – stats API 5xx`)
    console.log(`  → DEFECT P0: Admin stats endpoint returns 5xx`)
  } else if (statErrors.some(r => r.status === 404)) {
    console.log(`  → RESULT: FAIL – stats endpoint not found`)
    console.log(`  → DEFECT P1: Admin stats endpoint 404`)
  } else {
    console.log(`  → RESULT: PASS`)
  }
})

// ────────────────────────────────────────────────
// S11: Admin Users List
// ────────────────────────────────────────────────
test('S11 – Admin users list', async ({ page }) => {
  if (!ADMIN_TOKEN) {
    console.log(`\nS11 – BLOCKED: No admin token`)
    test.skip()
    return
  }

  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  // First test via API directly
  const usersRes = await fetch(`${API_URL}/api/v1/admin/users`, {
    headers: { 'Authorization': `Bearer ${ADMIN_TOKEN}` }
  })
  const usersStatus = usersRes.status
  const usersData = await usersRes.json().catch(() => null)

  console.log(`\nS11 – Admin Users List`)
  console.log(`  API GET /api/v1/admin/users: ${usersStatus}`)
  if (usersData && typeof usersData === 'object') {
    const count = Array.isArray(usersData) ? usersData.length : (usersData.total || usersData.count || '?')
    console.log(`  Users count: ${count}`)
  }

  if (usersStatus !== 200) {
    console.log(`  → DEFECT P0: Admin users API returns ${usersStatus}`)
  }

  // Now test UI
  await injectAdminSession(page)
  await page.goto(`${BASE_URL}/admin/users`, { waitUntil: 'networkidle' })
  const url = page.url()
  const body = await page.textContent('body') || ''
  const isLogin = url.includes('/login')
  const isBlank = body.trim().length < 100
  const showsUsers = body.includes('admin@tesigo.com') || body.includes('testuser@tesigo.com')

  const uiErrors = failedRequests.filter(r => r.url.includes('user') && r.status >= 400)
  console.log(`  UI URL: ${url}`)
  console.log(`  Shows user emails: ${showsUsers}`)
  console.log(`  UI API errors: ${uiErrors.map(r => `${r.status} ${r.url}`).join(', ') || 'none'}`)

  if (isLogin) {
    console.log(`  → RESULT: FAIL – redirected to login`)
    console.log(`  → DEFECT P0: Admin users page requires session that localStorage injection doesn't provide properly`)
  } else if (!showsUsers && !isBlank) {
    console.log(`  → RESULT: PARTIAL PASS – page loads but user emails not visible (may need pagination or different rendering)`)
  } else if (isBlank) {
    console.log(`  → RESULT: FAIL – blank screen`)
  } else {
    console.log(`  → RESULT: PASS`)
  }
})

// ────────────────────────────────────────────────
// S12: Admin Block/Unblock User (API)
// ────────────────────────────────────────────────
test('S12 – Admin block/unblock user (API + UI)', async ({ page }) => {
  if (!ADMIN_TOKEN) {
    console.log(`\nS12 – BLOCKED: No admin token`)
    test.skip()
    return
  }

  console.log(`\nS12 – Admin Block/Unblock User`)

  // Get user ID 2 (testuser)
  const usersRes = await fetch(`${API_URL}/api/v1/admin/users`, {
    headers: { 'Authorization': `Bearer ${ADMIN_TOKEN}` }
  })
  const usersData = await usersRes.json().catch(() => null) as any
  const usersList = Array.isArray(usersData) ? usersData : (usersData?.users || usersData?.items || usersData?.data || [])
  const testUser = usersList.find((u: any) => u.email === TEST_USER_EMAIL)

  if (!testUser) {
    console.log(`  → BLOCKED: testuser@tesigo.com not found in users list`)
    console.log(`  Users data: ${JSON.stringify(usersData).slice(0, 200)}`)
    return
  }

  const userId = testUser.id
  console.log(`  Test user ID: ${userId}, is_active: ${testUser.is_active}`)

  // Test block via API (uses PUT method)
  const blockRes = await fetch(`${API_URL}/api/v1/admin/users/${userId}/block`, {
    method: 'PUT',
    headers: { 'Authorization': `Bearer ${ADMIN_TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ reason: 'smoke test' })
  })
  console.log(`  PUT /api/v1/admin/users/${userId}/block: ${blockRes.status}`)
  if (!blockRes.ok) {
    const errBody = await blockRes.json().catch(() => null)
    console.log(`  Block error: ${JSON.stringify(errBody)}`)
    console.log(`  → DEFECT P0: Cannot block user – PUT /block returns ${blockRes.status}`)
  }

  // Test unblock (uses PUT method)
  const unblockRes = await fetch(`${API_URL}/api/v1/admin/users/${userId}/unblock`, {
    method: 'PUT',
    headers: { 'Authorization': `Bearer ${ADMIN_TOKEN}`, 'Content-Type': 'application/json' }
  })
  console.log(`  PUT /api/v1/admin/users/${userId}/unblock: ${unblockRes.status}`)
  if (!unblockRes.ok) {
    console.log(`  → DEFECT P0: Cannot unblock user – PUT /unblock returns ${unblockRes.status}`)
  }

  const overallOk = blockRes.ok && unblockRes.ok
  if (overallOk) {
    console.log(`  → RESULT: PASS – block/unblock API works`)
  } else {
    console.log(`  → RESULT: FAIL – block/unblock API failing`)
    console.log(`  → DEFECT P0: Admin block/unblock not functional`)
  }

  // Now check UI
  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)
  await injectAdminSession(page)
  await page.goto(`${BASE_URL}/admin/users`, { waitUntil: 'networkidle' })

  const blockBtnVisible = await page.locator('button:has-text("Block"), button:has-text("Unblock"), button:has-text("Заблокувати")').count() > 0
  console.log(`  Block/Unblock button in UI: ${blockBtnVisible}`)

  if (!blockBtnVisible && !page.url().includes('/login')) {
    console.log(`  → UI DEFECT P1: Block/Unblock button not visible in admin users table`)
  }
})

// ────────────────────────────────────────────────
// S13: Admin Make-Admin
// ────────────────────────────────────────────────
test('S13 – Admin make-admin action', async ({ page }) => {
  if (!ADMIN_TOKEN) {
    console.log(`\nS13 – BLOCKED: No admin token`)
    test.skip()
    return
  }

  console.log(`\nS13 – Admin Make-Admin`)

  // Check API – POST /make-admin with is_admin:true payload
  const makeAdminRes = await fetch(`${API_URL}/api/v1/admin/users/2/make-admin`, {
    method: 'POST',
    headers: { 'Authorization': `Bearer ${ADMIN_TOKEN}`, 'Content-Type': 'application/json' },
    body: JSON.stringify({ is_admin: true })
  })
  console.log(`  POST /api/v1/admin/users/2/make-admin (is_admin:true): ${makeAdminRes.status}`)

  if (makeAdminRes.ok) {
    // Revert - revoke admin
    const revokeRes = await fetch(`${API_URL}/api/v1/admin/users/2/revoke-admin`, {
      method: 'POST',
      headers: { 'Authorization': `Bearer ${ADMIN_TOKEN}`, 'Content-Type': 'application/json' }
    })
    console.log(`  POST /revoke-admin: ${revokeRes.status}`)
  } else {
    const errBody = await makeAdminRes.json().catch(() => null)
    console.log(`  Make-admin error: ${JSON.stringify(errBody)}`)
    console.log(`  → DEFECT P1: Make-admin endpoint fails with ${makeAdminRes.status}`)
  }

  const apiOk = makeAdminRes.ok
  if (apiOk) {
    console.log(`  → RESULT: PASS`)
  } else {
    // Check UI
    const { consoleErrors } = attachNetworkMonitor(page)
    await injectAdminSession(page)
    await page.goto(`${BASE_URL}/admin/users/2`, { waitUntil: 'networkidle' })
    const hasMakeAdminBtn = await page.locator('button:has-text("Make Admin"), text=Make Admin').count() > 0
    console.log(`  UI Make-Admin button: ${hasMakeAdminBtn}`)
    console.log(`  → RESULT: ${hasMakeAdminBtn ? 'PARTIAL PASS (UI has button)' : 'FAIL'}`)
  }
})

// ────────────────────────────────────────────────
// S14: Admin Logout
// ────────────────────────────────────────────────
test('S14 – Admin logout', async ({ page }) => {
  if (!ADMIN_TOKEN) {
    console.log(`\nS14 – BLOCKED: No admin token`)
    test.skip()
    return
  }

  const { consoleErrors, failedRequests } = attachNetworkMonitor(page)

  await injectAdminSession(page)
  await page.goto(`${BASE_URL}/admin/dashboard`, { waitUntil: 'networkidle' })
  const dashUrl = page.url()

  console.log(`\nS14 – Admin Logout`)
  console.log(`  Admin dashboard URL: ${dashUrl}`)

  if (dashUrl.includes('/login')) {
    console.log(`  → BLOCKED: Admin session not established via localStorage injection`)
    return
  }

  // Admin logout is inside a dropdown triggered by clicking the user avatar/email area
  // Try to open the dropdown first
  const avatarSelectors = [
    'button:has-text("A")',  // Admin avatar button (first letter)
    '[aria-label*="user"]', '[aria-label*="account"]',
  ]
  for (const sel of avatarSelectors) {
    const el = page.locator(sel).first()
    if (await el.isVisible().catch(() => false)) {
      await el.click()
      await page.waitForTimeout(600)
      break
    }
  }
  // After dropdown open, try clicking the admin@tesigo.com area to open dropdown
  const adminEmailBtn = page.locator('button').filter({ hasText: 'admin@tesigo.com' }).first()
  if (await adminEmailBtn.isVisible().catch(() => false)) {
    await adminEmailBtn.click()
    await page.waitForTimeout(600)
  }

  const logoutSelectors = [
    'button:has-text("Sign out")', 'button:has-text("Logout")',
    'a:has-text("Sign out")', 'a:has-text("Logout")',
    '[data-testid="admin-logout"]',
  ]

  let found = false
  for (const sel of logoutSelectors) {
    const el = page.locator(sel).first()
    if (await el.isVisible().catch(() => false)) {
      console.log(`  Found logout: ${sel}`)
      await el.click()
      await page.waitForTimeout(2000)
      found = true
      break
    }
  }

  if (!found) {
    // Screenshot page for debugging
    const body = await page.textContent('body') || ''
    console.log(`  Body snippet: ${body.slice(0, 200)}`)
    console.log(`  → RESULT: BLOCKED – no logout button found`)
    console.log(`  → DEFECT P1: Admin logout button not visible`)
    return
  }

  const afterUrl = page.url()
  const ok = afterUrl.includes('/login') || afterUrl.includes('/admin/login') || afterUrl === `${BASE_URL}/`
  console.log(`  After logout: ${afterUrl}`)
  console.log(`  → RESULT: ${ok ? 'PASS' : 'FAIL – unexpected URL ' + afterUrl}`)
})

// ────────────────────────────────────────────────
// EXTRA: FE→BE Contract Check (4xx/5xx scan)
// ────────────────────────────────────────────────
test('EXTRA – Key FE→BE contract endpoints', async ({ page }) => {
  console.log(`\nEXTRA – FE→BE Contract Checks`)

  if (!ADMIN_TOKEN && !USER_TOKEN) {
    console.log(`  BLOCKED: No tokens available`)
    return
  }

  const token = ADMIN_TOKEN || USER_TOKEN
  const endpoints = [
    { method: 'GET', path: '/api/v1/auth/me', token: USER_TOKEN || ADMIN_TOKEN, desc: 'Auth ME' },
    { method: 'GET', path: '/api/v1/documents', token: USER_TOKEN || ADMIN_TOKEN, desc: 'Documents list' },
    { method: 'GET', path: '/api/v1/payment/history', token: USER_TOKEN || ADMIN_TOKEN, desc: 'Payment history' },
    { method: 'GET', path: '/api/v1/refunds', token: USER_TOKEN || ADMIN_TOKEN, desc: 'Refunds list' },
    { method: 'GET', path: '/api/v1/admin/users', token: ADMIN_TOKEN, desc: 'Admin users' },
    { method: 'GET', path: '/api/v1/admin/stats', token: ADMIN_TOKEN, desc: 'Admin stats' },
    { method: 'POST', path: '/api/v1/generate/full-document', token: USER_TOKEN || ADMIN_TOKEN, desc: 'Generate (expect 422)' },
  ]

  for (const ep of endpoints) {
    if (!ep.token) {
      console.log(`  SKIP ${ep.method} ${ep.path} – no token`)
      continue
    }
    const res = await fetch(`${API_URL}${ep.path}`, {
      method: ep.method,
      headers: {
        'Authorization': `Bearer ${ep.token}`,
        'Content-Type': 'application/json',
      },
      body: ep.method === 'POST' ? JSON.stringify({}) : undefined
    })
    const ok = res.status < 500 && !(res.status === 404 || res.status === 405)
    const tag = ok ? '✅' : (res.status === 422 ? '⚠️' : '❌')
    console.log(`  ${tag} ${ep.method} ${ep.path} → ${res.status} (${ep.desc})`)
    if (!ok && res.status !== 422) {
      console.log(`     → DEFECT: ${ep.desc} endpoint broken (${res.status})`)
    }
  }
})
