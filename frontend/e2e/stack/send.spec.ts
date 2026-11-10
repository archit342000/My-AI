import { expect, test } from '@playwright/test';
import { botRows, startChat } from './helpers';

test('a plain turn is saved: one reply row, the same after a reload', async ({ page }) => {
  await startChat(page, 'NOTHINK say something');
  await expect(botRows(page)).toHaveCount(1);
  await expect(botRows(page).first()).toContainText('Plain answer with no reasoning.');
  await page.reload();
  await expect(botRows(page)).toHaveCount(1);
  await expect(botRows(page).first()).toContainText('Plain answer with no reasoning.');
  await expect(page.locator('.user-message')).toHaveCount(1);
});

test('the chat appears in the sidebar with its first message as title', async ({ page }) => {
  await startChat(page, 'NOTHINK sidebar title');
  await expect(page.locator('.chat-list-item', { hasText: 'NOTHINK sidebar title' })).toHaveCount(
    1,
  );
});
