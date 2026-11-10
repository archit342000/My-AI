import { expect, test } from '@playwright/test';
import { send, waitIdle } from './helpers';

// Fixed by the start-chat-and-send change: on develop a temporary chat's reply is not drawn on the landing page.
test('a temporary chat answers, is not listed, and can be saved', async ({ page }) => {
  test.fail(
    true,
    'develop does not show the temporary chat reply: fixed by the start-chat-and-send change',
  );
  await page.goto('/');
  await page.locator('#temp-chat-btn').click();
  await expect(page.locator('#temp-chat-banner')).toBeVisible();
  await send(page, 'NOTHINK temporary question');
  await waitIdle(page); // a temporary chat answers on the landing page
  await expect(page.locator('.bot-message').first()).toContainText(
    'Plain answer with no reasoning.',
  );
  // Not in the history while it is temporary.
  await expect(
    page.locator('.chat-list-item', { hasText: 'NOTHINK temporary question' }),
  ).toHaveCount(0);
  await page.locator('#save-temp-chat-btn').click();
  await expect(page.locator('#temp-chat-banner')).toHaveCount(0);
  await expect(
    page.locator('.chat-list-item', { hasText: 'NOTHINK temporary question' }),
  ).toHaveCount(1);
});
