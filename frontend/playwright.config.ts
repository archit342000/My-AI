import { defineConfig, devices } from '@playwright/test';

// Uses the system Chrome (see plans/frontend-react-migration notes); no browser download.
export default defineConfig({
  testDir: 'e2e',
  // The stack suite has its own config (playwright.stack.config.ts): it starts the real backend.
  testIgnore: 'stack/**',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'off',
    launchOptions: { executablePath: '/opt/google/chrome/chrome', args: ['--no-sandbox'] },
  },
  projects: [{ name: 'desktop', use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } } }],
});
