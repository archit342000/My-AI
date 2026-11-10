import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { expect, test, type Page } from '@playwright/test';

// A two-round reply (reasoning, a tool call and its result, then the answer) replaces the model.
// The completion is held back briefly so the box can be opened while the turn is still live.
const stream = readFileSync(
  fileURLToPath(new URL('../src/test/fixtures/stream/two-rounds.sse', import.meta.url)),
  'utf8',
);

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('my_ai_selected_model', 'Gemma4-26B-A4B-it-GGUF');
    localStorage.setItem('my_ai_selected_model_name', 'Gemma4-26B-A4B-it-GGUF');
  });
  await page.route('**/v1/chat/completions', async (route) => {
    await new Promise((resolve) => setTimeout(resolve, 1200));
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: stream });
  });
});

/** Stands in for the server persisting the turn: the chat detail returns the saved rows. */
async function persistedDetail(page: Page, sentText: string) {
  await page.route(/\/api\/chats\/(?!workspaces)[^/]+$/, async (route) => {
    if (route.request().method() !== 'GET') return route.fallback();
    const id = new URL(route.request().url()).pathname.split('/').pop();
    const base = { chat_id: id, parent_type: 'main', timestamp: 1 };
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id,
        title: sentText,
        is_running: false,
        messages: [
          { ...base, id: '1', role: 'user', content: sentText },
          {
            ...base,
            id: '2',
            role: 'assistant',
            content: 'Checking.',
            reasoning_content: 'Need to list files.',
            tool_calls: [
              { id: 'call_1', type: 'function', function: { name: 'list_files', arguments: '{}' } },
            ],
          },
          { ...base, id: '3', role: 'tool', tool_call_id: 'call_1', content: '3 files' },
          {
            ...base,
            id: '4',
            role: 'assistant',
            content: 'There are 3 files.',
            reasoning_content: 'Now answer.',
            model: 'Gemma4-26B-A4B-it-GGUF',
          },
        ],
      }),
    });
  });
}

test('a box opened while the turn streams stays open on the saved reply, and the full view lists the steps', async ({
  page,
}) => {
  const errors: string[] = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  await persistedDetail(page, 'List the files');
  await page.goto('/');
  await page.locator('#chat-textarea').fill('List the files');
  await page.keyboard.press('Enter');

  // Live: the header says Thinking... until the stream ends; open the box now.
  const live = page.locator('[data-live="true"]');
  await expect(live.locator('.thought-header-title')).toContainText(/thinking/i);
  await live.locator('.thought-toggle').click();
  await expect(live.locator('.thought-container.expanded')).toHaveCount(1);

  // Saved: the live row is gone, the same box is still open and says Thought process.
  await expect(page.locator('[data-live="true"]')).toHaveCount(0);
  const saved = page.locator('.bot-message').last();
  await expect(saved).toContainText('There are 3 files.');
  await expect(saved.locator('.thought-container.expanded')).toHaveCount(1);
  await expect(saved.locator('.thought-header-title')).toHaveText(/thought process/i);
  await expect(saved.locator('.thought-timeline-wrapper .activity-type')).toHaveText([
    'Reasoning',
    'Call: List Files',
    'Tool Result: List Files',
    'Reasoning',
  ]);
  await expect(page.locator('.tool-summary')).toHaveCount(0);

  // Full view: opens a dialog with every step and closes with Escape, returning focus to its button.
  const fullView = saved.locator('.thought-full-view-btn');
  await fullView.click();
  const dialog = page.getByRole('dialog');
  await expect(dialog.locator('.activity-type')).toHaveCount(4);
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(fullView).toBeFocused();
  expect(errors).toEqual([]);
});
