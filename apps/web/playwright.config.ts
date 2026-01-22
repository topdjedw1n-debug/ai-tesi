import { defineConfig, devices } from '@playwright/test'

/**
 * Playwright E2E Testing Configuration
 *
 * Real browser testing for critical user flows:
 * - Magic link authentication
 * - Document creation
 * - Payment checkout
 * - Dashboard stats
 * - Document list
 */

export default defineConfig({
  testDir: './e2e',

  // Test execution settings
  fullyParallel: false, // Run tests sequentially for stability
  forbidOnly: !!process.env.CI, // Fail on .only() in CI
  retries: process.env.CI ? 2 : 0, // Retry flaky tests in CI
  workers: process.env.CI ? 1 : 1, // Single worker for stability

  // Reporter configuration
  reporter: [
    ['html', { outputFolder: 'playwright-report' }],
    ['list'], // Console output
  ],

  // Shared test settings
  use: {
    // Base URL for tests
    baseURL: process.env.PLAYWRIGHT_BASE_URL || 'http://localhost:3000',

    // Browser behavior
    headless: process.env.CI ? true : false, // Show browser locally
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
    trace: 'retain-on-failure',

    // Timeouts
    actionTimeout: 10000, // 10s for actions
    navigationTimeout: 15000, // 15s for navigation
  },

  // Projects (browsers)
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],

  // Web server (start Next.js automatically)
  webServer: {
    command: 'npm run dev',
    url: 'http://localhost:3000',
    reuseExistingServer: !process.env.CI,
    timeout: 120000, // 2 minutes to start
    env: {
      NODE_ENV: 'test',
    },
  },
})
