import { expect, test, type Locator, type Page } from '@playwright/test';

// The phone layout (under 600px), checked at 390px. Geometry is read from the browser.

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

test('the header is a band of its own: its buttons are full touch size and messages scroll beneath it, not behind it', async ({
  page,
}) => {
  await longChat(page);
  await page.locator('#messages').evaluate((el) => el.scrollTo(0, 800));
  const menu = await rect(page.locator('.mobile-topbar'));
  const files = await rect(page.locator('#nav-files-btn'));
  const head = await rect(page.locator('.main-head'));
  for (const button of [menu, files]) {
    expect(button.width).toBeGreaterThanOrEqual(48);
    expect(button.height).toBeGreaterThanOrEqual(48);
    expect(button.y).toBeGreaterThanOrEqual(head.y);
    expect(button.bottom).toBeLessThanOrEqual(head.bottom + 1);
  }
  // Whatever is on top at points in the band is not a message.
  const points: Array<[number, number]> = [
    [menu.x + menu.width / 2, menu.y + menu.height / 2],
    [files.x + files.width / 2, files.y + files.height / 2],
    [195, head.y + head.height / 2],
    [10, head.y + 10],
    [380, head.bottom - 4],
  ];
  for (const point of points) {
    const insideMessage = await page.evaluate(
      ([px, py]) => Boolean(document.elementFromPoint(px ?? 0, py ?? 0)?.closest('.message-row')),
      point,
    );
    expect(insideMessage, `message visible at ${point.join(',')}`).toBe(false);
  }
  // The conversation starts under the band, and the title sits between the two buttons.
  expect((await rect(page.locator('#messages'))).y).toBeGreaterThanOrEqual(head.bottom - 1);
  const title = await rect(page.locator('.chat-title-display'));
  expect(title.x).toBeGreaterThanOrEqual(menu.right - 1);
  expect(title.right).toBeLessThanOrEqual(files.x + 1);
});

test('every screen runs edge to edge: the content panel has no inset, border or rounded corner', async ({
  page,
}) => {
  await longChat(page);
  const main = page.locator('main');
  const box = await rect(main);
  expect([box.x, box.y, box.width, box.height].map(Math.round)).toEqual([0, 0, 390, 844]);
  const style = await main.evaluate((el) => {
    const c = getComputedStyle(el);
    return [c.borderTopWidth, c.borderTopLeftRadius, c.boxShadow];
  });
  expect(style).toEqual(['0px', '0px', 'none']);
  expect(await overflow(page)).toBe(0);
});

test('the drawer shows all three actions, is opaque, and closes when the settings page opens', async ({
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
  const colour = await drawer.evaluate((el) => getComputedStyle(el).backgroundColor);
  expect(colour).toMatch(/^rgb\(/); // no see-through part
  // The menu button steps aside while the drawer is open.
  await expect(page.locator('.mobile-topbar')).toBeHidden();
  await page.locator('#system-settings-trigger').click();
  await expect(page.getByRole('region', { name: 'Settings' })).toBeVisible();
  await expect(drawer).toBeHidden();
});

test('the files button is switched off on the home page and absent on the logs page', async ({
  page,
}) => {
  await page.goto('/');
  await expect(page.locator('#nav-files-btn')).toBeDisabled();
  await page.goto('/logs');
  await expect(page.locator('#nav-files-btn')).toHaveCount(0);
  // The page's name is in the header band.
  await expect(page.locator('.main-head')).toContainText('Logs');
});

test('a brief message appears above the message box, not on it', async ({ page }) => {
  // A send the server refuses shows an error message.
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

test('the settings page fills the screen, a pop-up rises from the bottom as a sheet, and nothing overflows sideways', async ({
  page,
}) => {
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
    const settings = page.getByRole('region', { name: 'Settings' });
    const b = await settled(settings);
    expect([b.x, b.y, b.width, b.height].map(Math.round)).toEqual([0, 0, 390, 844]);
    expect(await overflow(page)).toBe(0);
    await settings.getByRole('button', { name: 'Back' }).click();
    await expect(settings).toHaveCount(0);
  }
  // A confirmation is a sheet: full width, attached to the bottom edge, rounded only at the top.
  await page.goto('/?settings=system');
  await page.getByRole('button', { name: 'Delete all', exact: true }).click();
  const sheet = page.locator('.modal-content').first();
  const s = await settled(sheet);
  expect(Math.round(s.x)).toBe(0);
  expect(Math.round(s.width)).toBe(390);
  expect(Math.round(s.bottom)).toBe(844);
  const corners = await sheet.evaluate((el) => {
    const c = getComputedStyle(el);
    return [c.borderBottomLeftRadius, c.borderBottomRightRadius, c.borderTopLeftRadius];
  });
  expect(corners.slice(0, 2)).toEqual(['0px', '0px']);
  expect(corners[2]).not.toBe('0px');
  expect(await overflow(page)).toBe(0);
});

test('a long model name stays inside its row, and the edit box fits in one row of buttons', async ({
  page,
}) => {
  const longName = 'a-very-long-model-name-that-would-not-fit-in-one-row-with-its-button.gguf';
  await page.route(/\/api\/models\/$/, (route) =>
    route.fulfill({ json: { data: [{ id: longName, status: { value: 'unloaded' } }] } }),
  );
  await page.goto('/?settings=models');
  const row = page.locator('#settings-models .crud-row').first();
  await expect(row).toBeVisible();
  const rowBox = await settled(row);
  const name = await rect(row.locator('.crud-title__name'));
  const button = await rect(row.getByRole('button'));
  expect(name.right).toBeLessThanOrEqual(rowBox.right);
  expect(button.right).toBeLessThanOrEqual(rowBox.right);
  expect(button.x).toBeGreaterThanOrEqual(name.x);
  expect(await overflow(page)).toBe(0);

  await longChat(page);
  await page.getByRole('button', { name: 'Edit message' }).click();
  const edit = await settled(page.locator('.edit-box'));
  expect(edit.right).toBeLessThanOrEqual(390);
  const ys = await Promise.all(
    ['Cancel', 'Save', 'Save and resend'].map(async (label) =>
      Math.round(
        (await rect(page.locator('.edit-box').getByRole('button', { name: label, exact: true }))).y,
      ),
    ),
  );
  expect(new Set(ys).size).toBe(1);
  expect(await overflow(page)).toBe(0);
});

/** Everything that can be pressed and is smaller than 48 (rule book Part 6). */
const smallTargets = (page: Page) =>
  page.evaluate(() => {
    const selector =
      'button, a[href], input:not([type=hidden]):not([type=file]):not([type=range]), [role=button], [role=switch], [role=radio], [role=checkbox], [role=tab], [role=combobox], [role=menuitem], [role=option]';
    const found: string[] = [];
    for (const el of Array.from(document.querySelectorAll<HTMLElement>(selector))) {
      const r = el.getBoundingClientRect();
      if (r.width === 0 || r.height === 0) continue;
      const style = getComputedStyle(el);
      if (style.visibility === 'hidden' || style.pointerEvents === 'none') continue;
      if (el.closest('[inert], [aria-hidden="true"]')) continue;
      // The message box is pressed as a whole: the field inside it is not a target of its own.
      if (el.id === 'chat-textarea') continue;
      // A link in a sentence of an answer keeps its line; a tick box's whole line is its target.
      if (
        el.closest('.message-content') &&
        (el.tagName === 'A' || el.matches('input[type=checkbox]'))
      )
        continue;
      if (r.height < 47.5 || r.width < 47.5)
        found.push(
          `${el.tagName.toLowerCase()}.${el.className} "${(el.getAttribute('aria-label') ?? el.textContent ?? '').trim().slice(0, 30)}" ${Math.round(r.width)}x${Math.round(r.height)}`,
        );
    }
    return found;
  });

test('everything that can be pressed is at least 48 on every screen', async ({ page }) => {
  await page.route(/\/api\/file_systems\?/, (route) =>
    route.fulfill({
      json: {
        file_systems: [
          { id: 'f1', title: 'notes.md', filename: 'notes.md', type: 'file', language: 'markdown' },
          { id: '', title: 'src', filename: 'src/', type: 'directory' },
        ],
      },
    }),
  );
  await page.route(/\/api\/file_systems\/f1(\?.*)?$/, (route) =>
    route.fulfill({
      json: { id: 'f1', title: 'notes.md', language: 'markdown', content: '# Notes\n\n- [ ] one' },
    }),
  );
  await page.goto('/');
  expect(await smallTargets(page), 'home').toEqual([]);
  await page.locator('.mobile-topbar').click();
  await settled(page.locator('#sidebar'));
  expect(await smallTargets(page), 'drawer').toEqual([]);
  await longChat(page);
  expect(await smallTargets(page), 'chat').toEqual([]);
  await page.getByRole('button', { name: 'AI tools' }).click();
  await settled(page.locator('.ui-sheet, .ui-popover').first());
  expect(await smallTargets(page), 'tools sheet').toEqual([]);
  await page.keyboard.press('Escape');
  await page.getByRole('button', { name: 'Files', exact: true }).click();
  await expect(page.getByRole('button', { name: /^notes.md/ })).toBeVisible();
  await settled(page.locator('.artifact-drawer')); // it arrives with a short animation
  expect(await smallTargets(page), 'files list').toEqual([]);
  await page.getByRole('button', { name: /^notes.md/ }).click();
  await expect(page.getByRole('heading', { name: 'Notes' })).toBeVisible();
  expect(await smallTargets(page), 'file open').toEqual([]);
  // A task line is its own target: the whole line, at least 48 tall.
  expect((await rect(page.locator('.fb-prev .task-list-item'))).height).toBeGreaterThanOrEqual(48);
  await page.goto('/?settings=chat');
  await settled(page.getByRole('region', { name: 'Settings' }));
  expect(await smallTargets(page), 'settings').toEqual([]);
  await page.goto('/logs');
  await expect(page.getByRole('radiogroup', { name: 'Which log' })).toBeVisible();
  expect(await smallTargets(page), 'logs').toEqual([]);
});

test('Back closes the newest layer first, and only then moves between pages', async ({ page }) => {
  await page.goto('/');
  await longChat(page);
  // A pop-up over a side panel over the page: Back undoes them in that order.
  await page.getByRole('button', { name: 'Files', exact: true }).click();
  const files = page.getByRole('complementary', { name: 'Files' });
  await expect(files).toBeVisible();
  await page.getByRole('button', { name: 'New file or folder' }).click();
  const sheet = page.locator('.ui-sheet');
  await expect(sheet).toBeVisible();
  await page.goBack();
  await expect(sheet).toHaveCount(0);
  await expect(files).toBeVisible();
  await page.goBack();
  await expect(files).toHaveCount(0);
  await expect(page).toHaveURL(/\/chat\/phone1$/);
  await expect(page.locator('.bot-message')).toBeVisible();

  // The drawer is a layer too.
  await page.locator('.mobile-topbar').click();
  await expect(page.locator('#sidebar')).toBeVisible();
  await page.goBack();
  await expect(page.locator('#sidebar')).toBeHidden();
  await expect(page).toHaveURL(/\/chat\/phone1$/);

  // A layer closed by its own button leaves no step behind: the next Back moves between pages.
  await page.locator('.mobile-topbar').click();
  await expect(page.locator('#sidebar')).toBeVisible();
  await page.locator('.sidebar-scrim').click({ position: { x: 370, y: 400 } });
  await expect(page.locator('#sidebar')).toBeHidden();
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
});

test('opened straight on a chat, Back goes Home before it leaves the app', async ({ page }) => {
  await page.route(/\/api\/chats\/phone1$/, (route) =>
    route.fulfill({
      json: { id: 'phone1', title: 'A long chat', is_running: false, messages: [] },
    }),
  );
  await page.goto('/chat/phone1');
  await expect(page).toHaveURL(/\/chat\/phone1$/);
  await expect(page.locator('#chat-textarea')).toBeVisible();
  await page.goBack();
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator('#welcome-hero')).toBeVisible();
});

test('with solid panels nothing on a phone screen blurs what is behind it', async ({ page }) => {
  await page.addInitScript(() => localStorage.setItem('my_ai_glass_mode', 'solid'));
  await longChat(page);
  await expect(page.locator('html')).toHaveAttribute('data-glass', 'solid');
  const blurred = () =>
    page.evaluate(() =>
      Array.from(document.querySelectorAll<HTMLElement>('body *'))
        .filter((el) => {
          const c = getComputedStyle(el);
          const filter = c.backdropFilter || c.getPropertyValue('-webkit-backdrop-filter');
          return filter && filter !== 'none';
        })
        .map((el) => `${el.tagName.toLowerCase()}.${el.className}`),
    );
  expect(await blurred()).toEqual([]);
  await page.locator('.mobile-topbar').click();
  await settled(page.locator('#sidebar'));
  expect(await blurred()).toEqual([]);
  await page.goto('/?settings=system');
  await expect(page.getByRole('region', { name: 'Settings' })).toBeVisible();
  expect(await blurred()).toEqual([]);
});

test('a long memory wraps inside its row: the settings page never scrolls sideways', async ({
  page,
}) => {
  const long =
    'Always read all the provided context fully before answering. Summarising or omitting in the name of efficiency is a catastrophic failure.';
  await page.route('**/api/tools/preferences', (route) =>
    route.fulfill({
      json: { preferences: [{ id: 'p1', content: long, tag: 'personal_info', timestamp: 1 }] },
    }),
  );
  await page.goto('/?settings=memory');
  const row = page.locator('.crud-row', { hasText: 'Always read all' });
  await expect(row).toBeVisible();
  const content = page.locator('.set-content');
  expect(await content.evaluate((el) => el.scrollWidth - el.clientWidth)).toBeLessThanOrEqual(0);
  expect(await overflow(page)).toBeLessThanOrEqual(0);
  const box = await rect(row);
  expect(box.right).toBeLessThanOrEqual(390);
  // The edit and delete buttons stay on screen beside the text.
  expect((await rect(row.getByRole('button').last())).right).toBeLessThanOrEqual(390);
});
