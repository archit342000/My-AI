import { expect, test, type Locator, type Page } from '@playwright/test';

// The phone layout (768px and below), checked at 390px. Geometry is read from the browser.

const rect = async (locator: Locator) => {
  const b = await locator.boundingBox();
  if (!b) throw new Error('element has no box');
  return { ...b, right: b.x + b.width, bottom: b.y + b.height };
};

/** Waits until the element has stopped moving (a drawer or dialog sliding in), then returns its box. */
async function settled(locator: Locator) {
  let previous = '';
  await expect
    .poll(async () => {
      const current = JSON.stringify(await locator.boundingBox());
      const same = current === previous;
      previous = current;
      return same;
    })
    .toBe(true);
  return rect(locator);
}

const overflow = (page: Page) =>
  page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('my_ai_selected_model', 'Gemma4-26B-A4B-it-GGUF');
    localStorage.setItem('my_ai_selected_model_name', 'Gemma4-26B-A4B-it-GGUF');
  });
});

const paragraphs = Array.from({ length: 40 }, (_, i) => `Paragraph ${i} of a long answer.`).join(
  '\n\n',
);

/** A saved chat with a long reply, answered by the page itself so no model is needed. */
async function longChat(page: Page) {
  await page.route(/\/api\/chats\/phone1$/, (route) =>
    route.fulfill({
      json: {
        id: 'phone1',
        title: 'A long chat',
        is_running: false,
        messages: [
          {
            id: '1',
            chat_id: 'phone1',
            role: 'user',
            content: 'Write a lot',
            parent_type: 'main',
            timestamp: 1,
          },
          {
            id: '2',
            chat_id: 'phone1',
            role: 'assistant',
            content: paragraphs,
            model: 'M',
            parent_type: 'main',
            timestamp: 2,
          },
        ],
      },
    }),
  );
  await page.goto('/chat/phone1');
  await expect(page.locator('.bot-message')).toContainText('Paragraph 39');
}

test('the assistant bubble uses the column width', async ({ page }) => {
  await longChat(page);
  const bubble = await rect(page.locator('.bot-message .message-content-wrapper'));
  expect(bubble.x).toBeLessThanOrEqual(30);
  expect(390 - bubble.right).toBeLessThanOrEqual(30);
});

test('the top bar is one opaque band: scrolled messages never show beside or behind its buttons', async ({
  page,
}) => {
  await longChat(page);
  await page.locator('#messages').evaluate((el) => el.scrollTo(0, 800));
  const menu = await rect(page.locator('.mobile-topbar'));
  const files = await rect(page.locator('#nav-files-btn'));
  // The menu button has the legacy size and place.
  expect([menu.x, menu.y, menu.width, menu.height].map(Math.round)).toEqual([20, 20, 56, 56]);
  // Whatever is on top at points in the band is not a message.
  const points: Array<[number, number]> = [
    [menu.x + menu.width / 2, menu.y + menu.height / 2],
    [files.x + files.width / 2, files.y + files.height / 2],
    [195, 70],
    [110, 40],
    [330, 76],
    [10, 40],
    [380, 10],
  ];
  for (const point of points) {
    const insideMessage = await page.evaluate(
      ([px, py]) => Boolean(document.elementFromPoint(px ?? 0, py ?? 0)?.closest('.message-row')),
      point,
    );
    expect(insideMessage, `message visible at ${point.join(',')}`).toBe(false);
  }
  // Both buttons are under the band's bottom edge and the title sits between them.
  expect(Math.max(menu.bottom, files.bottom)).toBeLessThanOrEqual(80);
  const title = await rect(page.locator('.chat-title-display'));
  expect(title.x).toBeGreaterThanOrEqual(menu.right);
  expect(title.right).toBeLessThanOrEqual(files.x);
});

test('the drawer shows all three actions, is opaque, and closes when a dialog opens', async ({
  page,
}) => {
  await page.goto('/');
  await page.locator('.mobile-topbar').click();
  const drawer = page.locator('#sidebar');
  await expect(drawer).toBeVisible();
  const box = await settled(drawer);
  for (const id of ['#new-chat-btn', '#temp-chat-btn', '#new-folder-btn']) {
    const b = await rect(page.locator(id));
    expect(b.x).toBeGreaterThanOrEqual(box.x);
    expect(b.right).toBeLessThanOrEqual(box.right);
  }
  const alpha = await drawer.evaluate((el) => getComputedStyle(el).backgroundColor);
  expect(alpha).not.toMatch(/rgba\(.*, 0(\.\d+)?\)$/);
  // The menu button steps aside while the drawer is open.
  await expect(page.locator('.mobile-topbar')).toBeHidden();
  await page.locator('#system-settings-trigger').click();
  await expect(page.getByRole('dialog', { name: 'System Settings' })).toBeVisible();
  await expect(drawer).toBeHidden();
});

test('the files button is dimmed on the home page and absent on the logs page', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.locator('#nav-files-btn')).toBeDisabled();
  await page.goto('/logs');
  await expect(page.locator('#nav-files-btn')).toHaveCount(0);
  const heading = await rect(page.getByRole('heading', { name: 'Logs' }));
  // The title is below the band, not under it.
  expect(heading.y).toBeGreaterThanOrEqual(80);
});

test('a toast appears above the composer, not on it', async ({ page }) => {
  // A send the server refuses shows an error toast (`/help` opens a dialog now, so it no longer does).
  await page.route('**/v1/chat/completions', (route) =>
    route.fulfill({ status: 500, json: { error: 'The model is unavailable' } }),
  );
  await page.goto('/');
  await page.locator('#chat-textarea').fill('hello');
  await page.keyboard.press('Enter');
  const toast = page.locator('.ui-toast').first();
  await expect(toast).toBeVisible();
  const composer = await rect(page.locator('.input-container'));
  expect((await rect(toast)).bottom).toBeLessThanOrEqual(composer.y);
});

test('dialogs fit the screen with a margin and nothing overflows sideways', async ({ page }) => {
  await page.goto('/');
  expect(await overflow(page)).toBe(0);
  await longChat(page);
  expect(await overflow(page)).toBe(0);
  await page.goto('/logs');
  expect(await overflow(page)).toBe(0);
  await page.goto('/');
  for (const trigger of ['#system-settings-trigger', '#settings-trigger']) {
    await page.locator('.mobile-topbar').click();
    await page.locator(trigger).click();
    const dialog = page.locator('.modal-content').first();
    await expect(dialog).toBeVisible();
    const b = await settled(dialog);
    expect(b.x).toBeGreaterThanOrEqual(7);
    expect(390 - b.right).toBeGreaterThanOrEqual(7);
    expect(b.y).toBeGreaterThanOrEqual(7);
    expect(844 - b.bottom).toBeGreaterThanOrEqual(7);
    expect(await overflow(page)).toBe(0);
    await page.keyboard.press('Escape');
    await expect(page.locator('.modal-content')).toHaveCount(0);
  }
});

test('model rows wrap to name, status and button, and the edit box fits in one row of buttons', async ({
  page,
}) => {
  const longName = 'a-very-long-model-name-that-would-not-fit-in-one-row-with-its-button.gguf';
  await page.route(/\/api\/models\/$/, (route) =>
    route.fulfill({ json: { data: [{ id: longName, status: { value: 'unloaded' } }] } }),
  );
  await page.goto('/');
  await page.locator('.mobile-topbar').click();
  await page.locator('#system-settings-trigger').click();
  await page.getByRole('button', { name: 'Model manager' }).click();
  const row = page.locator('.model-row').first();
  await expect(row).toBeVisible();
  const rowBox = await settled(row);
  const name = await rect(row.locator('.model-row__name'));
  const button = await rect(row.getByRole('button'));
  expect(name.y).toBeLessThan(button.y); // the name has its own line above the button
  expect(name.right).toBeLessThanOrEqual(rowBox.right);
  expect(button.right).toBeLessThanOrEqual(rowBox.right);
  expect(await overflow(page)).toBe(0);
  await page.keyboard.press('Escape');

  await longChat(page);
  await page.locator('.user-message').hover();
  await page.getByRole('button', { name: 'Edit message' }).click({ force: true });
  const edit = await settled(page.locator('.edit-box'));
  expect(edit.right).toBeLessThanOrEqual(390);
  const ys = await Promise.all(
    ['Cancel', 'Save', 'Save & regenerate'].map(async (label) =>
      Math.round(
        (await rect(page.locator('.edit-box').getByRole('button', { name: label, exact: true }))).y,
      ),
    ),
  );
  expect(new Set(ys).size).toBe(1); // the three buttons share one row
  expect(await overflow(page)).toBe(0);
});
