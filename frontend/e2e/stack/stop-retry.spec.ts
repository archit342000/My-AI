import { expect, test } from '@playwright/test';
import { botRows, send, startChat, waitIdle } from './helpers';

test('stopping keeps the partial reply and the send button comes back', async ({ page }) => {
  await page.goto('/');
  await send(page, 'SLOW write a lot');
  await expect(page).toHaveURL(/\/chat\/[a-z0-9]+$/);
  await expect(page.locator('[data-live="true"] .message-content').last()).toContainText(
    'Slow paragraph',
    { timeout: 30_000 },
  );
  await page.locator('#send-btn[aria-label="Stop generating"]').click();
  await waitIdle(page);
  // The partial text is still there and nothing is left running.
  await expect(page.locator('.bot-message').last()).toContainText('Slow paragraph');
  await expect(page.locator('#send-btn[aria-label="Send message"]')).toBeVisible();
});

test('Retry regenerates the reply: still one assistant row', async ({ page }) => {
  await startChat(page, 'NOTHINK first answer');
  await expect(botRows(page)).toHaveCount(1);
  await page.locator('.bot-message').last().getByRole('button', { name: 'Retry response' }).click();
  await waitIdle(page);
  await expect(botRows(page)).toHaveCount(1);
  await expect(botRows(page).first()).toContainText('Plain answer with no reasoning.');
  await expect(page.locator('.user-message')).toHaveCount(1);
});
