import { expect, test, type Page } from '@playwright/test';

// Every screen, at computer, tablet and phone widths, day and night: the page never scrolls sideways,
// nothing is logged as an error, and no words sit on the bare sphere without their fade behind them.

const SCREENS = [
  { name: 'home', path: '/' },
  { name: 'settings', path: '/?settings=chat' },
  { name: 'logs', path: '/logs' },
  { name: 'page not found', path: '/no-such-page' },
  { name: 'chat not found', path: '/chat/no-such-chat' },
] as const;

const SIZES = [
  { name: 'computer', width: 1440, height: 900 },
  { name: 'tablet', width: 820, height: 1100 },
  { name: 'phone', width: 390, height: 844 },
] as const;

const THEMES = ['light', 'dark'] as const;

/** Visible words whose nearest painted surface is the page itself (the sphere), not a panel or a fade. */
function wordsOnBareSphere(page: Page) {
  return page.evaluate(() => {
    const painted = (el: Element) => {
      if (el.classList.contains('on-sphere')) return true;
      const style = getComputedStyle(el);
      const filter = style.backdropFilter || style.getPropertyValue('-webkit-backdrop-filter');
      if (filter && filter !== 'none') return true;
      if (style.backgroundImage !== 'none') return true;
      const alpha = /rgba?\(([^)]+)\)/.exec(style.backgroundColor)?.[1]?.split(/[,/ ]+/)[3];
      return style.backgroundColor !== 'transparent' && (alpha === undefined || Number(alpha) > 0);
    };
    const found: string[] = [];
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    for (let node = walker.nextNode(); node; node = walker.nextNode()) {
      const text = node.textContent?.trim();
      const parent = node.parentElement;
      if (!text || !parent || parent.closest('script, style, [hidden], [aria-hidden="true"]')) {
        continue;
      }
      const box = parent.getBoundingClientRect();
      const style = getComputedStyle(parent);
      // Screen-reader-only text and anything not drawn does not count.
      if (box.width <= 1 || box.height <= 1 || style.visibility === 'hidden') continue;
      if (Number(style.opacity) === 0) continue;
      let el: Element | null = parent;
      let covered = false;
      while (el && el !== document.body && el !== document.documentElement) {
        if (painted(el)) {
          covered = true;
          break;
        }
        el = el.parentElement;
      }
      if (!covered) found.push(text.slice(0, 40));
    }
    return found;
  });
}

for (const theme of THEMES) {
  for (const size of SIZES) {
    for (const screen of SCREENS) {
      test(`${screen.name}, ${size.name}, ${theme}: fits, logs no error, keeps words off the bare sphere`, async ({
        page,
      }) => {
        const errors: string[] = [];
        page.on('console', (message) => {
          // A 404 for the chat that is not there is the point of that screen.
          if (message.type() === 'error' && !/Failed to load resource/.test(message.text())) {
            errors.push(message.text());
          }
        });
        page.on('pageerror', (error) => errors.push(error.message));
        await page.addInitScript((mode) => localStorage.setItem('my_ai_theme_mode', mode), theme);
        await page.setViewportSize({ width: size.width, height: size.height });
        await page.goto(screen.path);
        await expect(page.locator('#app-root')).toBeVisible();
        await expect(page.locator('.ui-skeleton')).toHaveCount(0);

        const sideways = await page.evaluate(
          () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
        );
        expect(sideways).toBeLessThanOrEqual(0);
        expect(await wordsOnBareSphere(page)).toEqual([]);
        expect(errors).toEqual([]);
      });
    }
  }
}
