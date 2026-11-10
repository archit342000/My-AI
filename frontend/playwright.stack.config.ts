import { defineConfig, devices } from '@playwright/test';

// The stack suite: the real backend (temporary data directory, static auth) with a scripted model, see e2e/stack/start-stack.mjs.
// Run with `npm run e2e:stack` after `npm run build`; it is not part of `scripts/check.sh`.
const port = Number(process.env.E2E_STACK_PORT ?? 5195);

export default defineConfig({
  testDir: 'e2e/stack',
  timeout: 90_000,
  fullyParallel: false,
  workers: 1,
  reporter: 'list',
  use: {
    baseURL: `http://127.0.0.1:${port}`,
    trace: 'off',
    launchOptions: { executablePath: '/opt/google/chrome/chrome', args: ['--no-sandbox'] },
  },
  webServer: {
    command: 'node e2e/stack/start-stack.mjs',
    url: `http://127.0.0.1:${port}/api/version`,
    timeout: 180_000,
    reuseExistingServer: false,
    // Let the launcher stop the backend and remove its data directory before Playwright gives up on it.
    gracefulShutdown: { signal: 'SIGTERM', timeout: 15_000 },
    stdout: 'ignore',
    stderr: 'pipe',
  },
  projects: [
    {
      name: 'desktop',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
  ],
});
