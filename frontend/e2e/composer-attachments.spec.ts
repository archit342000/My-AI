import { expect, test, type Page } from '@playwright/test';

// File staging in the composer. The upload and delete endpoints are answered by the page, so the test sees exactly
// which requests the UI makes and nothing is stored.

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('my_ai_selected_model', 'Gemma4-26B-A4B-it-GGUF');
    localStorage.setItem('my_ai_selected_model_name', 'Gemma4-26B-A4B-it-GGUF');
  });
});

async function mockFiles(page: Page) {
  const deleted: string[] = [];
  let uploads = 0;
  await page.route('**/api/files/upload', (route) => {
    uploads += 1;
    return route.fulfill({
      json: {
        success: true,
        file_id: `file-${uploads}`,
        original_filename: 'notes.txt',
        mime_type: 'text/plain',
        file_size: 3,
      },
    });
  });
  await page.route(/\/api\/files\/file-\d+$/, (route) => {
    if (route.request().method() === 'DELETE') {
      deleted.push(new URL(route.request().url()).pathname.split('/').pop() ?? '');
      return route.fulfill({ json: { success: true } });
    }
    return route.fallback();
  });
  return { deleted };
}

test('files staged for a new chat that is abandoned are deleted: New Chat leaves nothing behind', async ({
  page,
}) => {
  const { deleted } = await mockFiles(page);
  await page.goto('/');
  await page
    .locator('input[type=file]')
    .setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('abc') });
  await expect(page.locator('.composer-chips')).toContainText('notes.txt');
  await expect(page.locator('.composer-chips')).toContainText('Ready');
  await page.getByRole('button', { name: 'New Chat' }).click();
  await expect.poll(() => deleted).toEqual(['file-1']);
  await expect(page.locator('.composer-chips')).toHaveCount(0);
});

test('a chip stays with the chat it was uploaded for', async ({ page }) => {
  await mockFiles(page);
  await page.route(/\/api\/chats\/(?!workspaces)[^/]+$/, (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({ json: { id: 'x', title: 't', is_running: false, messages: [] } })
      : route.fallback(),
  );
  await page.goto('/chat/chat-a');
  await page
    .locator('input[type=file]')
    .setInputFiles({ name: 'notes.txt', mimeType: 'text/plain', buffer: Buffer.from('abc') });
  await expect(page.locator('.composer-chips')).toContainText('Ready');
  await page.evaluate(() => {
    window.history.pushState({}, '', '/chat/chat-b');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await expect(page.locator('.composer-chips')).toHaveCount(0);
  await page.evaluate(() => {
    window.history.pushState({}, '', '/chat/chat-a');
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
  await expect(page.locator('.composer-chips')).toContainText('notes.txt');
});

test('a file dropped on the page gets a chip', async ({ page }) => {
  await mockFiles(page);
  await page.goto('/');
  await expect(page.locator('#chat-textarea')).toBeVisible();
  await page.evaluate(() => {
    const data = new DataTransfer();
    data.items.add(new File(['abc'], 'dropped.txt', { type: 'text/plain' }));
    const main = document.querySelector('main');
    main?.dispatchEvent(
      new DragEvent('dragenter', { dataTransfer: data, bubbles: true, cancelable: true }),
    );
    main?.dispatchEvent(
      new DragEvent('drop', { dataTransfer: data, bubbles: true, cancelable: true }),
    );
  });
  await expect(page.locator('.composer-chips')).toContainText('dropped.txt');
});

test('/help opens a readable list of commands', async ({ page }) => {
  await page.goto('/');
  await page.locator('#chat-textarea').fill('/help');
  await page.keyboard.press('Enter');
  const dialog = page.getByRole('dialog', { name: 'Commands and skills' });
  await expect(dialog).toContainText('/skills');
  await page.keyboard.press('Escape');
  await expect(dialog).toHaveCount(0);
  await expect(page.locator('#chat-textarea')).toBeFocused();
});
