import { expect, test, type Page } from '@playwright/test';

// The theme is applied before first paint, and the particle canvas is visible in both themes.

async function recordThemeAtFirstRender(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as { __darkAtFirstRender?: boolean };
    const watch = new MutationObserver(() => {
      const root = document.getElementById('root');
      if (root && root.childElementCount > 0 && w.__darkAtFirstRender === undefined) {
        w.__darkAtFirstRender = document.documentElement.classList.contains('dark');
        watch.disconnect();
      }
    });
    watch.observe(document, { childList: true, subtree: true });
  });
}

async function setTheme(page: Page, mode: 'light' | 'dark') {
  await page.addInitScript((value) => localStorage.setItem('my_ai_theme_mode', value), mode);
}

test('with the dark theme saved, <html> is dark before the app renders anything', async ({
  page,
}) => {
  await setTheme(page, 'dark');
  await recordThemeAtFirstRender(page);
  await page.goto('/');
  await expect(page.locator('#root > *').first()).toBeVisible();
  expect(
    await page.evaluate(
      () => (window as unknown as { __darkAtFirstRender?: boolean }).__darkAtFirstRender,
    ),
  ).toBe(true);
});

const canvasHasPixels = (page: Page) =>
  page.evaluate(() => {
    const canvas = document.getElementById('bg-stars') as HTMLCanvasElement | null;
    const ctx = canvas?.getContext('2d');
    if (!canvas || !ctx) return false;
    const data = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
    for (let i = 3; i < data.length; i += 4) if ((data[i] ?? 0) > 0) return true;
    return false;
  });

for (const mode of ['light', 'dark'] as const) {
  for (const route of ['/', '/chat/theme1']) {
    test(`${mode} theme on ${route}: body is transparent and the particles are drawn`, async ({
      page,
    }) => {
      await setTheme(page, mode);
      await page.route(/\/api\/chats\/theme1$/, (r) =>
        r.fulfill({ json: { id: 'theme1', title: 't', is_running: false, messages: [] } }),
      );
      await page.goto(route);
      await expect(page.locator('#bg-stars')).toHaveCount(1);
      expect(await page.evaluate(() => getComputedStyle(document.body).backgroundColor)).toBe(
        'rgba(0, 0, 0, 0)',
      );
      // The canvas has painted something visible (a particle), not just an empty surface.
      await expect.poll(() => canvasHasPixels(page)).toBe(true);
    });
  }

  test(`${mode} theme: the logs page has no canvas and an opaque page background`, async ({
    page,
  }) => {
    await setTheme(page, mode);
    await page.goto('/logs');
    await expect(page.locator('#bg-stars')).toHaveCount(0);
    const html = await page.evaluate(
      () => getComputedStyle(document.documentElement).backgroundColor,
    );
    expect(html).not.toBe('rgba(0, 0, 0, 0)');
  });
}
