import { expect, test, type Page } from '@playwright/test';

// The files drawer: it sits beside the chat, asks before dropping edits, renames, and compares versions.
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
      const body = route.request().postDataJSON() as { title?: string };
      updates.push(body);
      if (file && body.title) file.title = body.title;
      return route.fulfill({ json: { success: true } });
    }
    return route.fulfill({ json: { ...file, content: `# ${file?.title}\nbody` } });
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

test('the drawer sits beside the chat: the composer ends before the drawer starts', async ({
  page,
}) => {
  await mockFiles(page);
  await page.goto('/chat/fa1');
  await page.getByRole('button', { name: 'View files and artifacts' }).click();
  // The chat narrows with a transition: wait until the composer has made room.
  await expect
    .poll(async () => {
      const drawer = await page.locator('.artifact-drawer').boundingBox();
      const composer = await page.locator('.input-container').boundingBox();
      return drawer && composer ? composer.x + composer.width <= drawer.x + 1 : false;
    })
    .toBe(true);
});

test('unsaved edits are guarded, a file can be renamed, and two versions can be compared', async ({
  page,
}) => {
  const { updates } = await mockFiles(page);
  await page.goto('/chat/fa1');
  await page.getByRole('button', { name: 'View files and artifacts' }).click();
  await page.getByRole('button', { name: /notes.md/ }).click();
  await page.getByRole('radio', { name: 'Edit' }).click();
  await page.locator('.cm-content').click();
  await page.keyboard.type('more');

  // Switching with an unsaved edit asks first; Cancel stays on the file.
  await page.getByRole('button', { name: /todo.md/ }).click();
  await expect(page.getByText('Discard unsaved changes?')).toBeVisible();
  await page.getByRole('button', { name: 'Cancel' }).click();
  await expect(page.locator('.artifact-viewer__title')).toHaveText('notes.md');

  // Rename through the More menu.
  await page.getByRole('button', { name: 'More file actions' }).click();
  await page.getByRole('menuitem', { name: 'Rename' }).click();
  await page.getByRole('dialog', { name: 'Rename file' }).getByRole('textbox').fill('plan.md');
  await page
    .getByRole('dialog', { name: 'Rename file' })
    .getByRole('button', { name: 'Rename' })
    .click();
  await expect.poll(() => updates).toContainEqual(expect.objectContaining({ title: 'plan.md' }));

  // Save the edit, so opening the history does not ask to discard it.
  await page.getByRole('button', { name: 'Save' }).click();
  await expect(page.getByRole('button', { name: 'Save' })).toHaveCount(0);

  // Version history compares an older version with the current one.
  await page.getByRole('button', { name: 'Versions' }).click();
  await page.locator('button:not([disabled])', { hasText: 'Compare with current' }).first().click();
  await expect(page.getByText('1 added, 1 removed')).toBeVisible();
});
