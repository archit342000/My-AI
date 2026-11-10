import { readFileSync } from 'node:fs';
import { expect, test } from '@playwright/test';
import { startChat } from './helpers';

// Key rectangles of the chat against numbers recorded from the legacy UI (geometry.json), 1px tolerance.
// A key listed under `expectedFail` is a known difference: it is reported, and the spec fails once it matches,
// so the list can only shrink.
type Rect = { x: number; y: number; width: number; height: number };
type Geometry = {
  legacy: Record<string, Record<string, Rect | null>>;
  expectedFail: Record<string, string[]>;
};
const geometry: Geometry = JSON.parse(
  readFileSync(new URL('./geometry.json', import.meta.url), 'utf8'),
);

const SELECTORS: Record<string, string> = {
  messages: '#messages',
  userMessage: '.user-message',
  botAvatar: '.bot-message .avatar',
  botContent: '.bot-message .message-content-wrapper .message-content',
  inputContainer: '.input-container',
  attachButton: '#attach-btn',
  toolsButton: '#tools-button',
  sendButton: '#send-btn',
};

const VIEWPORTS = {
  desktop: { width: 1440, height: 900 },
  phone: { width: 390, height: 844 },
} as const;

const matches = (a: Rect, b: Rect) =>
  (['x', 'y', 'width', 'height'] as const).every((k) => Math.abs(a[k] - b[k]) <= 1);

for (const [name, viewport] of Object.entries(VIEWPORTS)) {
  test(`chat geometry at ${name} size matches the recorded legacy rectangles`, async ({ page }) => {
    await page.setViewportSize(viewport);
    await startChat(page, 'LONG write a lot');
    // Scroll to the top and wait until it sticks (the transcript may still be pinning itself to the bottom).
    await expect
      .poll(() =>
        page.locator('#messages').evaluate((el) => {
          el.scrollTo({ top: 0, behavior: 'instant' });
          return el.scrollTop;
        }),
      )
      .toBe(0);
    const measured = await page.evaluate((selectors) => {
      const out: Record<string, Rect | null> = {};
      for (const [key, selector] of Object.entries(selectors)) {
        const el = document.querySelector(selector);
        if (!el) {
          out[key] = null;
          continue;
        }
        const r = el.getBoundingClientRect();
        out[key] = {
          x: Math.round(r.x),
          y: Math.round(r.y),
          width: Math.round(r.width),
          height: Math.round(r.height),
        };
      }
      return out;
    }, SELECTORS);

    const known = new Set(geometry.expectedFail[name] ?? []);
    const wrong: string[] = [];
    const fixed: string[] = [];
    for (const [key, legacy] of Object.entries(geometry.legacy[name] ?? {})) {
      const rect = measured[key];
      const ok = Boolean(rect && legacy && matches(rect, legacy));
      if (known.has(key)) {
        if (ok) fixed.push(key);
        else
          test.info().annotations.push({
            type: 'known difference',
            description: `${key}: ${JSON.stringify(rect)} vs legacy ${JSON.stringify(legacy)}`,
          });
      } else if (!ok) {
        wrong.push(`${key}: ${JSON.stringify(rect)} vs legacy ${JSON.stringify(legacy)}`);
      }
    }
    expect(wrong, 'these differ from the legacy rectangles by more than 1px').toEqual([]);
    expect(fixed, 'these now match: remove them from expectedFail in geometry.json').toEqual([]);
  });
}
