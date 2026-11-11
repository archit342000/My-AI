import { expect, test, type Page } from '@playwright/test';

// The Files panel: it sits beside the chat, saves edits by itself, renames, compares versions and goes full screen.
// The file-system endpoints are answered by the page, so nothing is stored.

type Entry = { id: string; title: string; filename: string; type: string; language: string };

async function mockFiles(page: Page) {
  const files: Entry[] = [
    { id: 'f1', title: 'notes.md', filename: 'notes.md', type: 'file', language: 'markdown' },
    { id: 'f2', title: 'todo.md', filename: 'todo.md', type: 'file', language: 'markdown' },
  ];
  const updates: unknown[] = [];
  await page.route(/\/api\/chats\/(?!workspaces)[^/]+$/, (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({ json: { id: 'fa1', title: 't', is_running: false, messages: [] } })
      : route.fallback(),
  );
  await page.route(/\/api\/file_systems\?/, (route) =>
    route.fulfill({ json: { file_systems: files } }),
  );
  await page.route(/\/api\/file_systems\/f\d(\?.*)?$/, async (route) => {
    const id = new URL(route.request().url()).pathname.split('/').pop() ?? '';
    const file = files.find((f) => f.id === id);
    if (route.request().method() === 'PATCH') {
      const body = route.request().postDataJSON() as { title?: string; content?: string };
      updates.push({ id, ...body });
      if (file && body.title) file.title = body.title;
      return route.fulfill({ json: { success: true } });
    }
    // todo.md is long, so the editor has somewhere to scroll.
    const body =
      id === 'f2' ? Array.from({ length: 300 }, (_, n) => `line ${n + 1}`).join('\n') : 'body';
    return route.fulfill({ json: { ...file, content: `# ${file?.title}\n${body}` } });
  });
  await page.route(/\/api\/file_systems\/f1\/versions(\?.*)?$/, (route) =>
    route.fulfill({
      json: {
        versions: [
          { version_number: 1, author: 'user', timestamp: 1700000000, comment: '' },
          { version_number: 2, author: 'user', timestamp: 1700000100, comment: 'edit' },
        ],
      },
    }),
  );
  await page.route(/\/api\/file_systems\/f1\/current-version/, (route) =>
    route.fulfill({ json: { current_version: 2 } }),
  );
  await page.route(/\/api\/file_systems\/f1\/diff/, (route) =>
    route.fulfill({
      json: {
        success: true,
        added_lines: ['new'],
        removed_lines: ['old'],
        stats: { lines_added: 1, lines_removed: 1 },
      },
    }),
  );
  return { updates };
}

test('the panel sits beside the chat: the message box ends before the panel starts', async ({
  page,
}) => {
  await mockFiles(page);
  await page.goto('/chat/fa1');
  await page.getByRole('button', { name: 'Files', exact: true }).click();
  await expect
    .poll(async () => {
      const drawer = await page.locator('.artifact-drawer').boundingBox();
      const composer = await page.locator('.input-container').boundingBox();
      return drawer && composer ? composer.x + composer.width <= drawer.x + 1 : false;
    })
    .toBe(true);
});

test('edits save by themselves, a file can be renamed, and two versions can be compared', async ({
  page,
}) => {
  const { updates } = await mockFiles(page);
  await page.goto('/chat/fa1');
  await page.getByRole('button', { name: 'Files', exact: true }).click();
  await page.getByRole('button', { name: /^notes.md/ }).click();
  await page.getByRole('radio', { name: 'Code' }).click();
  await page.locator('.cm-content').click();
  await page.keyboard.press('Control+End');
  await page.keyboard.type(' more');
  await expect(page.getByRole('button', { name: 'Save', exact: true })).toHaveCount(0);

  // Going back to the list saves what was typed, without a question.
  await page.getByRole('button', { name: 'Back to the file list' }).click();
  await expect(page.getByRole('button', { name: /^todo.md/ })).toBeVisible();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect
    .poll(() => updates)
    .toContainEqual(expect.objectContaining({ id: 'f1', content: '# notes.md\nbody more' }));

  // Rename from the row's own menu.
  await page.getByRole('button', { name: 'More for notes.md' }).click();
  await page.getByRole('menuitem', { name: /Rename or move/ }).click();
  const popup = page.getByRole('dialog', { name: 'Rename or move' });
  await popup.getByLabel('File name').fill('plan.md');
  await popup.getByRole('button', { name: 'Save' }).click();
  await expect
    .poll(() => updates)
    .toContainEqual(expect.objectContaining({ id: 'f1', title: 'plan.md' }));

  // Version history compares an older version with the current one.
  await page.getByRole('button', { name: /^plan.md/ }).click();
  await expect(page.getByText('v2')).toBeVisible();
  await page.getByRole('button', { name: 'Version history' }).click();
  const history = page.getByRole('dialog', { name: 'Version history' });
  await history.getByRole('button', { name: /^Version 1/ }).click();
  await history.getByRole('button', { name: 'Compare with current' }).click();
  await expect(page.getByText('1 added, 1 removed')).toBeVisible();
});

test('full screen fills the window and returns exactly where it was', async ({ page }) => {
  await mockFiles(page);
  await page.goto('/chat/fa1');
  await page.getByRole('button', { name: 'Files', exact: true }).click();
  // A width of the user's own, set from the keyboard.
  await page.getByRole('separator', { name: 'Drag to resize the files panel' }).press('ArrowLeft');
  await page.getByRole('button', { name: /^todo.md/ }).click();
  await page.getByRole('radio', { name: 'Code' }).click();
  const scroller = page.locator('.cm-scroller');
  await scroller.evaluate((el) => (el.scrollTop = 900));
  /** The line at the top of the editor: where the reader is, whatever the editor's own pixel sums say. */
  const topLine = () =>
    scroller.evaluate((el) => {
      const top = el.getBoundingClientRect().top;
      const lines = Array.from(el.querySelectorAll('.cm-line'));
      return lines.find((line) => line.getBoundingClientRect().bottom > top + 1)?.textContent ?? '';
    });
  // The editor settles its measurements after a jump: wait until the top line stops changing.
  let seen = '';
  await expect
    .poll(async () => {
      const now = await topLine();
      const same = now !== '' && now === seen;
      seen = now;
      return same;
    })
    .toBe(true);
  const before = {
    width: (await page.locator('.artifact-drawer').boundingBox())?.width,
    line: await topLine(),
  };
  expect(before.line).toMatch(/^line \d+$/);

  await page.getByRole('button', { name: 'Full screen' }).click();
  const layer = page.getByRole('dialog', { name: 'Files, full screen' });
  await expect(layer).toBeVisible();
  // It arrives with a short animation: wait until it covers the window.
  const size = page.viewportSize();
  await expect
    .poll(async () => {
      const box = await layer.boundingBox();
      return [box?.width, box?.height];
    })
    .toEqual([size?.width, size?.height]);
  // The list and the editor are side by side, on the same file.
  await expect(layer.getByRole('button', { name: /^notes.md/ })).toBeVisible();
  await expect(layer.locator('.fb-name')).toHaveText('todo.md');

  await layer.getByRole('button', { name: 'Back' }).click();
  await expect(layer).toHaveCount(0);
  await expect(page.locator('.artifact-drawer .fb-name')).toHaveText('todo.md');
  await expect.poll(topLine).toBe(before.line);
  expect((await page.locator('.artifact-drawer').boundingBox())?.width).toBe(before.width);
});
