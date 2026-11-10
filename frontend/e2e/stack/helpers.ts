import { expect, type Page } from '@playwright/test';

/** Types a message on the open page and sends it. */
export async function send(page: Page, text: string) {
  const box = page.locator('#chat-textarea');
  await box.fill(text);
  await box.press('Enter');
}

/** Waits until no reply is being generated (the live row is gone and the button offers Send again). */
export async function waitIdle(page: Page) {
  await expect(page.locator('[data-live="true"]')).toHaveCount(0, { timeout: 60_000 });
  await expect(page.locator('#send-btn[aria-label="Send message"]')).toBeVisible({
    timeout: 60_000,
  });
}

/** Starts a chat from the landing page and returns once its reply has finished. */
export async function startChat(page: Page, text: string) {
  await page.goto('/');
  await send(page, text);
  await expect(page).toHaveURL(/\/chat\/[a-z0-9]+$/);
  // The URL changes before the turn starts: wait for the reply row so "idle" cannot be seen too early.
  await expect(page.locator('.bot-message')).not.toHaveCount(0, { timeout: 30_000 });
  await waitIdle(page);
}

export const botRows = (page: Page) => page.locator('.bot-message');
