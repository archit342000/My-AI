import { expect, test, type Page } from '@playwright/test';

// The app runs with AUTH_PROVIDER=static, so the real /api/me answers as the admin. A user is simulated by
// answering /api/me in the browser (page.route), which is what the per-user storage keys depend on.

const USER_A = { id: 'user-a', email: 'a@test.io', role: 'user' };
const USER_B = { id: 'user-b', email: 'b@test.io', role: 'user' };

async function actAs(page: Page, user: typeof USER_A | null) {
  await page.unroute('/api/me').catch(() => undefined);
  if (user) await page.route('/api/me', (route) => route.fulfill({ json: user }));
}

async function openSystemSettings(page: Page) {
  await page.getByRole('button', { name: 'System settings' }).click();
  await expect(page.getByRole('dialog', { name: 'System Settings' })).toBeVisible();
}

test('admin sees the signed-in email and the admin controls', async ({ page }) => {
  await page.goto('/');
  await expect(page.locator('.sidebar-user')).toBeVisible();
  await expect(page.getByRole('link', { name: 'Logs' })).toBeVisible();
  await openSystemSettings(page);
  await expect(page.getByText('Code runner', { exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: 'Model manager' })).toBeVisible();
});

test('a user sees no admin controls', async ({ page }) => {
  await actAs(page, USER_A);
  await page.goto('/');
  await expect(page.getByText(USER_A.email)).toBeVisible();
  await expect(page.getByRole('link', { name: 'Logs' })).toHaveCount(0);
  await openSystemSettings(page);
  await expect(page.getByText('Code runner', { exact: true })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Model manager' })).toHaveCount(0);
  await expect(page.getByRole('button', { name: 'Skills' })).toBeVisible();
  await page.goto('/logs');
  await expect(page.getByText('Not available')).toBeVisible();
});

test("one user's chat settings do not reach another user or the admin", async ({ page }) => {
  // user A turns Vision input on
  await actAs(page, USER_A);
  await page.goto('/');
  await openSystemSettings(page);
  await page.getByLabel('Vision input').check();
  expect(await page.evaluate(() => localStorage.getItem('my_ai_vision_enabled:user-a'))).toBe('true');

  // user B starts from the defaults
  await actAs(page, USER_B);
  await page.goto('/');
  await openSystemSettings(page);
  await expect(page.getByLabel('Vision input')).not.toBeChecked();
  expect(await page.evaluate(() => localStorage.getItem('my_ai_vision_enabled:user-b'))).toBeNull();

  // the admin (the real /api/me) keeps the original key names and is untouched by A's choice
  await actAs(page, null);
  await page.goto('/');
  await openSystemSettings(page);
  await expect(page.getByLabel('Vision input')).not.toBeChecked();
  expect(await page.evaluate(() => localStorage.getItem('my_ai_vision_enabled'))).toBeNull();
});
