import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { expect, test } from '@playwright/test';

// The completion endpoint is replaced with a recorded stream so the test does not depend on
// the local model being loaded. The UI path (composer -> store -> render) is real.
const basic = readFileSync(fileURLToPath(new URL('../src/test/fixtures/stream/basic.sse', import.meta.url)), 'utf8');

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('my_ai_selected_model', 'Gemma4-26B-A4B-it-GGUF');
    localStorage.setItem('my_ai_selected_model_name', 'Gemma4-26B-A4B-it-GGUF');
  });
  await page.route('**/v1/chat/completions', (route) =>
    route.fulfill({ status: 200, contentType: 'text/event-stream', body: basic }),
  );
});

/** Stands in for the server persisting the turn: the chat detail returns the saved messages. */
async function persistedDetail(page: import('@playwright/test').Page, sentText: string) {
  await page.route(/\/api\/chats\/(?!workspaces)[^/]+$/, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    const id = new URL(route.request().url()).pathname.split('/').pop();
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id,
        title: sentText,
        is_running: false,
        messages: [
          { id: '1', chat_id: id, role: 'user', content: sentText, parent_type: 'main' },
          { id: '2', chat_id: id, role: 'assistant', content: 'Hello there, friend!', parent_type: 'main', model: 'Gemma4-26B-A4B-it-GGUF' },
        ],
      }),
    });
  });
}

test('sends a message and renders the streamed reply', async ({ page }) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => (m.type() === 'error' ? errors.push(m.text()) : undefined));

  await persistedDetail(page, 'Say hello');
  await page.goto('/');
  await page.locator('#chat-textarea').fill('Say hello');
  await page.keyboard.press('Enter');

  await expect(page).toHaveURL(/\/chat\/[a-z0-9]+$/);
  await expect(page.locator('.bot-message').last()).toContainText('Hello there, friend!');
  await expect(page.locator('[data-live="true"]')).toHaveCount(0);
  expect(errors.filter((e) => !e.includes('favicon'))).toEqual([]);
});
