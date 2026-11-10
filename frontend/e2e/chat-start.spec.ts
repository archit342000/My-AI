import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { expect, test, type Page } from '@playwright/test';

// The completion stream is recorded; the create call (PATCH) is held until the test releases it and the
// chat does not exist on the server (404) until then, which is the race that used to show an error page.
const basic = readFileSync(fileURLToPath(new URL('../src/test/fixtures/stream/basic.sse', import.meta.url)), 'utf8');

async function mockServer(page: Page, sentText: string) {
  let created = false;
  let release: () => void = () => undefined;
  const gate = new Promise<void>((resolve) => (release = resolve));
  await page.route('**/v1/chat/completions', (route) => {
    created = true; // the server creates the chat on the first turn too
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body: basic });
  });
  await page.route(/\/api\/chats\/(?!workspaces)[^/]+$/, async (route) => {
    const id = new URL(route.request().url()).pathname.split('/').pop();
    if (route.request().method() === 'PATCH') {
      await gate;
      created = true;
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    }
    if (route.request().method() !== 'GET') return route.fallback();
    if (!created) {
      return route.fulfill({ status: 404, contentType: 'application/json', body: '{"error":"Chat not found"}' });
    }
    return route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id,
        title: sentText,
        is_running: false,
        messages: [
          { id: '1', chat_id: id, role: 'user', content: sentText, parent_type: 'main' },
          { id: '2', chat_id: id, role: 'assistant', content: 'Hello there, friend!', parent_type: 'main', model: 'M' },
        ],
      }),
    });
  });
  return release;
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('my_ai_selected_model', 'Gemma4-26B-A4B-it-GGUF');
    localStorage.setItem('my_ai_selected_model_name', 'Gemma4-26B-A4B-it-GGUF');
  });
});

test('the first send shows no error, keeps focus and lists the chat at once', async ({ page }) => {
  const releaseCreate = await mockServer(page, 'Say hello');
  await page.goto('/');
  await page.locator('#chat-textarea').fill('Say hello');
  await page.keyboard.press('Enter');
  await page.keyboard.type('and more');

  // While the create call is still pending: the message is on screen, nothing is wrong, the
  // composer kept focus and the text typed after sending, and the chat is listed and highlighted.
  await expect(page).toHaveURL(/\/chat\/[a-z0-9]+$/);
  await expect(page.locator('.user-message').first()).toContainText('Say hello');
  await expect(page.getByRole('alert')).toHaveCount(0);
  await expect(page.locator('#chat-textarea')).toBeFocused();
  await expect(page.locator('#chat-textarea')).toHaveValue('and more');
  await expect(page.locator('#sidebar .chat-list-item.active')).toContainText('Say hello');

  releaseCreate();
  await expect(page.locator('.bot-message').last()).toContainText('Hello there, friend!');
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('a temporary chat sends and streams its reply', async ({ page }) => {
  (await mockServer(page, 'Say hello'))();
  await page.goto('/');
  await page.getByRole('button', { name: 'Temporary chat' }).first().click();
  await page.locator('#chat-textarea').fill('Say hello');
  await page.keyboard.press('Enter');
  await expect(page.getByText('Hello there, friend!').first()).toBeVisible();
  await expect(page.getByRole('alert')).toHaveCount(0);
});
