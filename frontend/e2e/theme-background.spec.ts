import { expect, test, type Page } from '@playwright/test';

// The theme is applied before first paint, and the particle canvas is visible in both themes.

async function recordThemeAtFirstRender(page: Page) {
  await page.addInitScript(() => {
    const w = window as unknown as {
      __darkAtFirstRender?: boolean;
      __themeAtFirstRender?: string;
      __glassAtFirstRender?: string;
    };
    const watch = new MutationObserver(() => {
      const root = document.getElementById('root');
      if (root && root.childElementCount > 0 && w.__darkAtFirstRender === undefined) {
        w.__darkAtFirstRender = document.documentElement.classList.contains('dark');
        w.__themeAtFirstRender = document.documentElement.dataset.theme;
        w.__glassAtFirstRender = document.documentElement.dataset.glass;
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

test('data-theme and data-glass are set before the app renders, from the saved choices', async ({
  page,
}) => {
  await setTheme(page, 'dark');
  await page.addInitScript(() => localStorage.setItem('my_ai_glass_mode', 'solid'));
  await recordThemeAtFirstRender(page);
  await page.goto('/');
  await expect(page.locator('#root > *').first()).toBeVisible();
  const first = await page.evaluate(() => {
    const w = window as unknown as { __themeAtFirstRender?: string; __glassAtFirstRender?: string };
    return { theme: w.__themeAtFirstRender, glass: w.__glassAtFirstRender };
  });
  expect(first).toEqual({ theme: 'dark', glass: 'solid' });
  // The shared values are in force: the near-black night.
  expect(
    await page.evaluate(() => getComputedStyle(document.documentElement).backgroundColor),
  ).toBe('rgb(7, 7, 8)');
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

test('solid panels: nothing on the page blurs what is behind it', async ({ page }) => {
  const blurred = () =>
    page.evaluate(
      () =>
        [...document.querySelectorAll('*')].filter((el) => {
          const style = getComputedStyle(el);
          return style.backdropFilter !== 'none' && style.backdropFilter !== '';
        }).length,
    );
  await page.goto('/');
  await expect(page.locator('#sidebar')).toBeVisible();
  expect(await blurred(), 'frosted is the default here, so something blurs').toBeGreaterThan(0);

  await page.evaluate(() => localStorage.setItem('my_ai_glass_mode', 'solid'));
  await page.reload();
  await expect(page.locator('#sidebar')).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.dataset.glass)).toBe('solid');
  expect(await blurred()).toBe(0);
});

test('a browser that cannot blur gets solid panels by itself', async ({ page }) => {
  await page.addInitScript(() => {
    const real = CSS.supports.bind(CSS);
    CSS.supports = ((a: string, b?: string) =>
      /backdrop-filter/.test(a)
        ? false
        : b === undefined
          ? real(a)
          : real(a, b)) as typeof CSS.supports;
  });
  await page.goto('/');
  await expect(page.locator('#root > *').first()).toBeVisible();
  expect(await page.evaluate(() => document.documentElement.dataset.glass)).toBe('solid');
});

test('with no saved theme the page follows the system setting', async ({ page }) => {
  for (const scheme of ['dark', 'light'] as const) {
    await page.emulateMedia({ colorScheme: scheme });
    await page.goto('/');
    await expect(page.locator('#root > *').first()).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe(scheme);
  }
});

test('the three typefaces come from the app, and no font host is contacted', async ({ page }) => {
  // Any font file, or anything at all from a font host, that does not come from the app itself.
  const fontHosts: string[] = [];
  page.on('request', (request) => {
    const url = new URL(request.url());
    const foreignFont =
      request.resourceType() === 'font' && url.origin !== new URL(page.url()).origin;
    if (foreignFont || /fonts\.(googleapis|gstatic)\.com/.test(url.host))
      fontHosts.push(request.url());
  });
  await page.goto('/');
  await expect(page.locator('#root > *').first()).toBeVisible();
  const loaded = await page.evaluate(async () => {
    const families = ['Sora', 'Instrument Sans', 'JetBrains Mono'];
    await Promise.all(families.map((family) => document.fonts.load(`16px "${family}"`)));
    return families.filter((family) =>
      [...document.fonts].some(
        (face) => face.family.replace(/"/g, '') === family && face.status === 'loaded',
      ),
    );
  });
  expect(loaded).toEqual(['Sora', 'Instrument Sans', 'JetBrains Mono']);
  expect(await page.evaluate(() => getComputedStyle(document.body).fontFamily)).toContain(
    'Instrument Sans',
  );
  expect(fontHosts).toEqual([]);
});

test('less motion: the particle canvas is drawn once and stands still', async ({ page }) => {
  const snapshot = () =>
    page.evaluate(() => {
      const canvas = document.getElementById('bg-stars') as HTMLCanvasElement;
      return canvas.toDataURL();
    });
  await page.emulateMedia({ reducedMotion: 'reduce' });
  await page.goto('/');
  await expect.poll(() => canvasHasPixels(page)).toBe(true);
  const before = await snapshot();
  await page.mouse.move(300, 300);
  await page.mouse.move(900, 500);
  await page.waitForTimeout(800);
  expect(await snapshot()).toBe(before);
  expect(await page.evaluate(() => document.getAnimations().length)).toBe(0);
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
