import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { expect, test, type Page } from '@playwright/test';

const fixture = (name: string) =>
  readFileSync(
    fileURLToPath(new URL(`../src/test/fixtures/stream/${name}.sse`, import.meta.url)),
    'utf8',
  );

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('my_ai_selected_model', 'Gemma4-26B-A4B-it-GGUF');
    localStorage.setItem('my_ai_selected_model_name', 'Gemma4-26B-A4B-it-GGUF');
  });
});

function chatDetail(id: string, over: Record<string, unknown> = {}) {
  return {
    id,
    title: 'Notes chat',
    is_running: false,
    messages: [{ id: '1', chat_id: id, role: 'user', content: 'write notes', parent_type: 'main' }],
    ...over,
  };
}

async function mockChat(page: Page, id: string, detail: () => Record<string, unknown>) {
  await page.route(`**/api/chats/${id}`, (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(detail()),
        })
      : route.fallback(),
  );
}

test('a banner offers to resume an interrupted turn and the turn continues', async ({ page }) => {
  let resumed = false;
  await mockChat(page, 'resume1', () => chatDetail('resume1', { resume_needed: !resumed }));
  await page.route('**/api/chats/resume1/resume', (route) => {
    resumed = true;
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body: fixture('basic') });
  });
  await page.goto('/chat/resume1');
  await expect(
    page.getByText('This conversation was interrupted. Resume where it left off?'),
  ).toBeVisible();
  await page.getByRole('button', { name: 'Resume' }).click();
  await expect(page.getByText('This conversation was interrupted.')).toHaveCount(0);
  expect(resumed).toBe(true);
});

test('files written during a turn show up in the opened files panel and a file link selects the file', async ({
  page,
}) => {
  let written = false;
  await mockChat(page, 'files1', () =>
    chatDetail('files1', {
      file_system_mode: 1,
      messages: [
        {
          id: '1',
          chat_id: 'files1',
          role: 'user',
          content: 'write the file',
          parent_type: 'main',
        },
        ...(written
          ? [
              {
                id: '2',
                chat_id: 'files1',
                role: 'assistant',
                content: 'I created the file.\n\nSee [hello](notes/hello.md) for details.',
                parent_type: 'main',
                model: 'M',
              },
            ]
          : []),
      ],
    }),
  );
  await page.route('**/v1/chat/completions', (route) => {
    written = true;
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body: fixture('files') });
  });
  await page.route(/\/api\/file_systems\?.*chat_id=files1/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        file_systems: written
          ? [
              {
                id: 'f1',
                title: 'notes/hello.md',
                filename: 'hello.md',
                folder: 'notes',
                type: 'file',
                language: 'markdown',
              },
            ]
          : [],
      }),
    }),
  );
  await page.route(/\/api\/file_systems\/f1\?/, (route) =>
    route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 'f1',
        title: 'notes/hello.md',
        language: 'markdown',
        content: '# Hello from the file',
      }),
    }),
  );

  await page.goto('/chat/files1');
  await page.locator('#chat-textarea').fill('write the file');
  await page.keyboard.press('Enter');

  // The panel opens by itself and lists the new file, with no reload.
  await expect(page.locator('.artifact-drawer')).toBeVisible();
  await expect(page.locator('.artifact-drawer')).toContainText('hello.md');

  // The link in the reply (notes/hello.md) selects the file in the panel.
  await page.locator('#messages').getByRole('link', { name: 'hello' }).click();
  await expect(page).toHaveURL(/\/chat\/files1$/);
  await expect(page.getByRole('heading', { name: 'Hello from the file' })).toBeVisible();
});
