import { expect, test } from '@playwright/test';

// N12 regression: the artifact overlay must not leave a blank strip beside its content.
// blank = overlay width minus the horizontal span of its visible descendants (pass when < 100 px).

const VIEWPORTS = [
  { width: 1280, height: 800 },
  { width: 375, height: 812 },
];

for (const viewport of VIEWPORTS) {
  test(`no blank strip beside artifact content at ${viewport.width}x${viewport.height}`, async ({
    page,
    request,
  }) => {
    const chatId = `n12-${Date.now()}`;
    const created = await request.post('/api/file_systems', {
      data: {
        chat_id: chatId,
        title: 'seed.md',
        content: '# seed\n'.repeat(40),
        file_system_type: 'custom',
        language: 'markdown',
      },
    });
    expect(created.ok()).toBeTruthy();

    await page.setViewportSize(viewport);
    await page.goto(`/chat/${chatId}`);
    await page.getByRole('button', { name: 'View files and artifacts' }).click();

    const overlay = page.locator('.artifact-drawer');
    await expect(overlay).toBeVisible();

    const blank = await page.evaluate(() => {
      const root = document.querySelector('.artifact-drawer') as HTMLElement;
      const box = root.getBoundingClientRect();
      let left = Infinity;
      let right = -Infinity;
      for (const el of Array.from(root.querySelectorAll<HTMLElement>('*'))) {
        const b = el.getBoundingClientRect();
        if (b.width === 0 || b.height === 0) continue;
        left = Math.min(left, b.left);
        right = Math.max(right, b.right);
      }
      const union = right === -Infinity ? 0 : right - left;
      return box.width - union;
    });

    expect(blank).toBeLessThan(100);
  });
}
