import { expect, test, type Page } from '@playwright/test';

// A keyboard that overlays the page only shrinks the visual viewport. Playwright cannot open a real keyboard, so
// the spec shrinks `visualViewport.height` by 300px and fires its resize event, as the browser would.

const KEYBOARD = 300;

async function openLongChat(page: Page) {
  const body = Array.from({ length: 60 }, (_, i) => `Paragraph ${i} of a long reply.`).join('\n\n');
  await page.route(/\/api\/chats\/kb1$/, (route) =>
    route.fulfill({
      json: {
        id: 'kb1',
        title: 'A long chat',
        is_running: false,
        messages: [
          {
            id: '1',
            chat_id: 'kb1',
            role: 'user',
            content: 'Write a lot',
            parent_type: 'main',
            timestamp: 1,
          },
          {
            id: '2',
            chat_id: 'kb1',
            role: 'assistant',
            content: body,
            model: 'M',
            parent_type: 'main',
            timestamp: 2,
          },
        ],
      },
    }),
  );
  await page.goto('/chat/kb1');
  await expect(page.locator('.bot-message')).toContainText('Paragraph 59');
}

async function openKeyboard(page: Page) {
  await page.evaluate((height) => {
    const viewport = window.visualViewport;
    if (!viewport) throw new Error('no visual viewport');
    Object.defineProperty(viewport, 'height', {
      configurable: true,
      get: () => window.innerHeight - height,
    });
    viewport.dispatchEvent(new Event('resize'));
  }, KEYBOARD);
}

test('the viewport meta lets the layout resize with the keyboard and blocks zoom', async ({
  page,
}) => {
  await page.goto('/');
  const content = await page.locator('meta[name=viewport]').getAttribute('content');
  expect(content).toContain('interactive-widget=resizes-content');
  expect(content).toContain('user-scalable=no');
});

test('with a keyboard over the page the composer rises and the last message stays above it', async ({
  page,
}) => {
  await openLongChat(page);
  // The composer follows the keyboard only on a touch screen: the emulated phone must report a coarse pointer.
  expect(await page.evaluate(() => window.matchMedia('(pointer: coarse)').matches)).toBe(true);
  await page.locator('#chat-textarea').focus();
  await openKeyboard(page);
  // The composer is raised to the top of the keyboard; the reader at the bottom is scrolled to the end again.
  await expect
    .poll(async () => {
      const composer = await page.locator('#chat-input-area').boundingBox();
      const visibleBottom = await page.evaluate(
        () => (window.visualViewport?.height ?? 0) + (window.visualViewport?.offsetTop ?? 0),
      );
      return composer ? Math.abs(composer.y + composer.height - visibleBottom) <= 24 : false;
    })
    .toBe(true);
  await expect
    .poll(async () => {
      const composer = await page.locator('#chat-input-area').boundingBox();
      const last = await page.locator('.bot-message').last().boundingBox();
      return composer && last ? last.y + last.height <= composer.y + 1 : false;
    })
    .toBe(true);
});
