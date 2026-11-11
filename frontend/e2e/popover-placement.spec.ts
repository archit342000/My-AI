import { expect, test, type Locator, type Page } from '@playwright/test';

// Popovers sit on their anchor and stay inside the visible screen. Geometry is read from the browser.

const box = async (locator: Locator) => {
  const b = await locator.boundingBox();
  if (!b) throw new Error('element has no box');
  return { ...b, right: b.x + b.width, bottom: b.y + b.height };
};

async function openTools(page: Page) {
  await page.goto('/');
  await page.getByRole('button', { name: 'AI tools' }).click();
  const panel = page.getByRole('dialog', { name: 'AI tools' });
  await expect(panel).toBeVisible();
  await page.waitForTimeout(400); // the panel animates in: measure it once it has settled
  return panel;
}

test('on a desktop screen the tools menu is 8px above the wrench, at any window height', async ({
  page,
}) => {
  for (const height of [900, 600]) {
    await page.setViewportSize({ width: 1440, height });
    const panel = await openTools(page);
    const wrench = await box(page.locator('#tools-button'));
    const sheet = await box(panel);
    expect(Math.abs(wrench.y - sheet.bottom - 8)).toBeLessThanOrEqual(1);
  }
});

test('on a phone the tools menu is a sheet above the composer, 8px from the screen edges', async ({
  page,
}) => {
  await page.setViewportSize({ width: 390, height: 844 });
  const panel = await openTools(page);
  const sheet = await box(panel);
  const composer = await box(page.locator('.input-container'));
  expect(sheet.bottom).toBeLessThanOrEqual(composer.y - 7);
  expect(Math.abs(sheet.x - 8)).toBeLessThanOrEqual(1);
  expect(Math.abs(390 - sheet.right - 8)).toBeLessThanOrEqual(1);
});

test('the model select keeps its search field inside the panel', async ({ page }) => {
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.goto('/');
  await page.locator('#settings-trigger').click();
  await page.getByRole('combobox', { name: 'Model', exact: true }).click();
  await page.waitForTimeout(400);
  const list = await box(page.locator('.ui-popover').last());
  const search = await box(page.locator('.ui-select__search'));
  expect(search.right).toBeLessThanOrEqual(list.right);
  expect(search.x).toBeGreaterThanOrEqual(list.x);
});

test('a chat context menu opened low in the sidebar lies inside the screen', async ({ page }) => {
  const chats = Array.from({ length: 30 }, (_, i) => ({
    id: `chat${i}`,
    title: `Chat ${i}`,
    updated_at: 1000 - i,
    is_running: false,
  }));
  await page.route(/\/api\/chats$/, (route) =>
    route.request().method() === 'GET' ? route.fulfill({ json: chats }) : route.fallback(),
  );
  await page.setViewportSize({ width: 1280, height: 700 });
  await page.goto('/');
  const last = page.locator('.chat-list-item').last();
  await last.scrollIntoViewIfNeeded();
  // The pointer position as the page saw it (the list may scroll while the click lands).
  await page.evaluate(() => {
    document.addEventListener(
      'contextmenu',
      (e) => ((window as unknown as { __y: number }).__y = e.clientY),
      { once: true },
    );
  });
  await last.click({ button: 'right', position: { x: 20, y: 10 } });
  const pointerY = await page.evaluate(() => (window as unknown as { __y: number }).__y);
  const menu = page.getByRole('menu').first();
  // The menu animates in: read where it sits once it has settled.
  await expect(menu).toBeVisible();
  await page.waitForTimeout(400);
  const settled = await box(menu);
  // Low on the screen the menu flips upward and its bottom edge is 4px above the pointer.
  if (settled.bottom < pointerY)
    expect(Math.abs(settled.bottom - (pointerY - 4))).toBeLessThanOrEqual(1);
  expect(settled.y).toBeGreaterThanOrEqual(0);
  expect(settled.bottom).toBeLessThanOrEqual(700);
  expect(settled.right).toBeLessThanOrEqual(1280);
});
