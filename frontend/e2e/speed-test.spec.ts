import { expect, test, type Page } from '@playwright/test';

// The speed test unloads the shared inference server's models, so these specs answer
// /api/models/test-speed in the browser and never reach a real model. The model list is answered too.

const STREAM =
  'data: {"test_status": "Unloading existing models..."}\n\ndata: {"test_status": "Loading model..."}\n\ndata: {"test_status": "Starting Turn 1 (Current Context: 0/8000)"}\n\ndata: {"choices": [{"delta": {"content": "Hello"}}]}\n\ndata: {"choices": [{"delta": {"content": " world"}}]}\n\ndata: {"timings": {"prompt_ms": 500, "prompt_n": 1000, "predicted_ms": 2000, "predicted_n": 100}, "usage": {"total_tokens": 1100}}\n\ndata: {"test_status": "Starting Turn 2 (Current Context: 1100/8000)"}\n\ndata: {"choices": [{"delta": {"content": "More"}}]}\n\ndata: {"timings": {"prompt_ms": 1000, "prompt_n": 3000, "predicted_ms": 4000, "predicted_n": 100}, "usage": {"total_tokens": 4200}}\n\ndata: {"test_status": "Completed: reached the target context"}\n\ndata: [DONE]\n\n';

async function openSpeedTest(page: Page) {
  await page.route('**/api/models/', (route) =>
    route.fulfill({ json: { data: [{ id: 'Stub/Model', status: { value: 'loaded' } }] } }),
  );
  await page.goto('/');
  await page.getByRole('button', { name: 'System settings' }).click();
  await page.getByRole('button', { name: 'Model manager' }).click();
  await page.getByRole('combobox', { name: 'Speed test target' }).click();
  await page.getByRole('option', { name: /Stub\/Model/ }).click();
  await page.getByRole('button', { name: 'Run speed test' }).click();
  await page.getByRole('button', { name: 'Run', exact: true }).click();
}

test('the speed test shows its figures and a chart', async ({ page }) => {
  await page.route('**/api/models/test-speed', (route) =>
    route.fulfill({ contentType: 'text/event-stream', body: STREAM }),
  );
  await openSpeedTest(page);
  await expect(page.getByRole('status').filter({ hasText: 'Completed' })).toBeVisible();
  const figures = page.locator('.speed-test__figures');
  await expect(figures).toContainText('4,200');
  await expect(figures).toContainText('37.50 tok/s');
  await expect(page.locator('.speed-chart__dot')).toHaveCount(2);
});

test('a running speed test can be stopped', async ({ page }) => {
  // The route never answers, so the run stays open until Stop aborts the request.
  await page.route('**/api/models/test-speed', () => new Promise<void>(() => undefined));
  await openSpeedTest(page);
  await page.getByRole('button', { name: 'Stop' }).click();
  await expect(page.getByRole('status').filter({ hasText: 'Stopped' })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Stop' })).toHaveCount(0);
});
