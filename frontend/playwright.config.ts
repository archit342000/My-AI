import { defineConfig, devices } from '@playwright/test';

// Uses the system Chrome (see plans/frontend-react-migration notes); no browser download.
export default defineConfig({
  testDir: 'e2e',
  timeout: 60_000,
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:5173',
    trace: 'off',
    launchOptions: { executablePath: '/opt/google/chrome/chrome', args: ['--no-sandbox'] },
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
      testIgnore: /mobile-(layout|keyboard)\.spec\.ts/,
    },
    {
      // A 390px phone screen in Chrome (touch, mobile viewport): the layout rules at 768px and below, and the
      // on-screen keyboard (simulated in the spec).
      name: 'phone',
      use: {
        ...devices['Desktop Chrome'],
        viewport: { width: 390, height: 844 },
        isMobile: true,
        hasTouch: true,
      },
      testMatch: /mobile-(layout|keyboard)\.spec\.ts/,
    },
  ],
});
