import { expect, test } from '@playwright/test';

// F1: New workspace in the navigation panel asks for a name, creates the workspace and opens its page.
test('New workspace creates a workspace and opens its page', async ({ page }) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'New workspace' }).click();
  const popup = page.getByRole('dialog', { name: 'New workspace' });
  await popup.getByRole('textbox').fill('E2E workspace');
  await popup.getByRole('button', { name: 'Create workspace' }).click();
  await expect(page).toHaveURL(/\/workspace\/[^/]+$/);
  await expect(page.getByRole('heading', { name: 'E2E workspace', exact: true })).toBeVisible();
});
