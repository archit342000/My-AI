import { expect, test } from '@playwright/test';

// F1: New Workspace in the sidebar asks for a name, creates the workspace and opens its page.
test('New Workspace creates a workspace and opens its page', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'New Workspace' }).click();
  await page.getByRole('textbox').fill('E2E workspace');
  await page.getByRole('button', { name: 'Create' }).click();
  await expect(page).toHaveURL(/\/workspace\/[^/]+$/);
  await expect(page.getByRole('heading', { name: 'E2E workspace', exact: true })).toBeVisible();
});
