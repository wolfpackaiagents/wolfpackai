import { defineConfig, devices } from '@playwright/test'

const baseURL = process.env.E2E_BASE_URL || 'http://127.0.0.1:5174'

export default defineConfig({
  testDir: './tests/e2e',
  forbidOnly: !!process.env.CI,
  fullyParallel: false,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? [['html', { open: 'never' }], ['list']] : 'list',
  use: {
    baseURL,
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: {
    command: 'npm run dev -- --host 127.0.0.1 --port 5174',
    url: baseURL,
    reuseExistingServer: !process.env.CI || Boolean(process.env.E2E_BASE_URL),
    timeout: 30_000,
    env: { WOLFPACK_API_URL: process.env.WOLFPACK_API_URL || 'http://127.0.0.1:8000' },
  },
})
