import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { expect, test, type Page } from '@playwright/test';

// The completion stays open (never answered) so the turn is still running when Stop is pressed, and
// the stop request takes 1.5s to answer. The server's chat is rolled back to the user message.
const basic = readFileSync(
  fileURLToPath(new URL('../src/test/fixtures/stream/basic.sse', import.meta.url)),
  'utf8',
);
const STOP_DELAY_MS = 1500;

async function mockServer(page: Page) {
  const events: string[] = [];
  let chatId = '';
  // The server still counts the old turn for a moment after the stop answers: the first send or
  // Retry after that is refused once as "in progress".
  let refuseOnce = false;
  const refusal = {
    status: 400,
    contentType: 'application/json',
    body: JSON.stringify({ error: 'a response is already in progress' }),
  };
  // What the server has stored: the user message, plus whatever finished turns added.
  const stored: Array<{ role: string; content: string }> = [{ role: 'user', content: 'Hold on' }];
  const reply = { role: 'assistant', content: 'Hello there, friend!' };
  await page.route('**/v1/chat/completions', async (route) => {
    events.push('completion');
    if (events.filter((e) => e === 'completion').length === 1) await new Promise(() => undefined); // held open until Stop
    if (refuseOnce) {
      refuseOnce = false;
      return route.fulfill(refusal);
    }
    const sent = (
      route.request().postDataJSON() as { messages?: Array<{ content?: string }> }
    ).messages?.at(-1)?.content;
    stored.push({ role: 'user', content: sent ?? 'Next one' }, reply);
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: basic });
  });
  await page.route('**/api/chats/*/stop', async (route) => {
    events.push('stop');
    await new Promise((r) => setTimeout(r, STOP_DELAY_MS));
    events.push('stop-answered');
    refuseOnce = true;
    await route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
  });
  await page.route('**/api/chats/*/resume', async (route) => {
    events.push('resume');
    if (refuseOnce) {
      refuseOnce = false;
      return route.fulfill(refusal);
    }
    stored.push(reply);
    await route.fulfill({ status: 200, contentType: 'text/event-stream', body: basic });
  });
  await page.route(/\/api\/chats\/(?!workspaces)[^/]+$/, async (route) => {
    const request = route.request();
    chatId = new URL(request.url()).pathname.split('/').pop() ?? chatId;
    if (request.method() === 'DELETE') {
      events.push('delete');
      return route.fulfill({ status: 200, contentType: 'application/json', body: '{}' });
    }
    if (request.method() === 'GET') {
      events.push('chat-get');
      return route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: chatId,
          title: 'Hold on',
          is_running: false,
          messages: stored.map((m, i) => ({
            id: String(i + 1),
            chat_id: chatId,
            parent_type: 'main',
            ...m,
          })),
        }),
      });
    }
    return route.fallback(); // PATCH creates the chat on the real backend
  });
  await page.route(/\/api\/chats$/, (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({
          status: 200,
          contentType: 'application/json',
          body: JSON.stringify(
            chatId ? [{ id: chatId, title: 'Hold on', timestamp: 1, workspace_id: null }] : [],
          ),
        })
      : route.fallback(),
  );
  return events;
}

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('my_ai_selected_model', 'Gemma4-26B-A4B-it-GGUF');
    localStorage.setItem('my_ai_selected_model_name', 'Gemma4-26B-A4B-it-GGUF');
  });
});

async function startAndStop(page: Page) {
  await page.goto('/');
  await page.locator('#chat-textarea').fill('Hold on');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Stop generating' })).toBeVisible();
  await page.getByRole('button', { name: 'Stop generating' }).click();
  // Until the server has answered the stop, the chat is busy.
  await expect(page.getByRole('button', { name: 'Stopping' })).toBeDisabled();
  await expect(page.locator('.bot-message')).toHaveCount(1);
  await expect(page.getByRole('button', { name: 'Retry' })).toBeDisabled();
}

test('Retry after Stop waits for the server and is then not refused', async ({ page }) => {
  const events = await mockServer(page);
  await startAndStop(page);
  const getsBeforeAnswer = events.filter((e) => e === 'chat-get').length;
  await expect(page.getByRole('button', { name: 'Retry' })).toBeEnabled({
    timeout: STOP_DELAY_MS + 3000,
  });
  expect(events.indexOf('stop-answered')).toBeGreaterThan(-1);
  // the chat was refetched only after the stop was answered
  expect(
    events.slice(0, events.indexOf('stop-answered')).filter((e) => e === 'chat-get').length,
  ).toBe(getsBeforeAnswer);
  await expect(page.locator('.bot-message')).toHaveCount(1);
  await page.getByRole('button', { name: 'Retry' }).click();
  await expect(page.locator('.bot-message').last()).toContainText('Hello there, friend!');
  // refused once right after the stop, repeated, then accepted: no refusal reaches the user
  expect(events.filter((e) => e === 'resume')).toHaveLength(2);
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('a new message after Stop starts a turn and no refusal appears', async ({ page }) => {
  const events = await mockServer(page);
  await startAndStop(page);
  await expect(page.getByRole('button', { name: 'Send message' })).toBeVisible({
    timeout: STOP_DELAY_MS + 3000,
  });
  await page.locator('#chat-textarea').fill('Next one');
  await page.keyboard.press('Enter');
  await expect(page.locator('.bot-message').last()).toContainText('Hello there, friend!');
  expect(events.filter((e) => e === 'completion')).toHaveLength(3);
  await expect(page.getByRole('alert')).toHaveCount(0);
});

test('deleting the chat that is generating stops it first', async ({ page }) => {
  const events = await mockServer(page);
  await page.goto('/');
  await page.locator('#chat-textarea').fill('Hold on');
  await page.keyboard.press('Enter');
  await expect(page.getByRole('button', { name: 'Stop generating' })).toBeVisible();
  await page.locator('.chat-list-item').first().click({ button: 'right' });
  await page.getByRole('menuitem', { name: /Delete/ }).click();
  await page.getByRole('button', { name: 'Delete', exact: true }).click();
  await expect.poll(() => events.includes('delete'), { timeout: STOP_DELAY_MS + 4000 }).toBe(true);
  expect(events.indexOf('stop-answered')).toBeGreaterThan(-1);
  expect(events.indexOf('stop-answered')).toBeLessThan(events.indexOf('delete'));
  await expect(page).toHaveURL(/\/$/);
  await expect(page.getByRole('button', { name: 'Send message' })).toBeVisible();
});
