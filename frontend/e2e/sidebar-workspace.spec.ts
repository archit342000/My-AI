import { expect, test, type Page } from '@playwright/test';

// The sidebar remembers its state and the workspace page fits a phone. Workspaces and chats are answered by the page.

/** Waits until an element has stopped moving or resizing (an animation), then returns its box. */
async function settledBox(page: Page, selector: string) {
  let previous = '';
  await expect
    .poll(async () => {
      const current = JSON.stringify(await page.locator(selector).boundingBox());
      const same = current === previous;
      previous = current;
      return same;
    })
    .toBe(true);
  return page.locator(selector).boundingBox();
}

async function mockData(page: Page) {
  await page.route(/\/api\/chats\/workspaces$/, (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({ json: [{ id: 'w1', name: 'Research', icon: null }] })
      : route.fallback(),
  );
  await page.route(/\/api\/chats$/, (route) =>
    route.request().method() === 'GET'
      ? route.fulfill({
          json: [{ id: 'c1', title: 'Paper draft', workspace_id: 'w1', timestamp: 1700000000 }],
        })
      : route.fallback(),
  );
}

test('the sidebar remembers its collapsed state and its width across a reload', async ({
  page,
}) => {
  await mockData(page);
  await page.goto('/');
  await page.locator('#sidebar-toggle').click();
  await expect(page.locator('#sidebar.sidebar-collapsed')).toHaveCount(1);
  await page.reload();
  await expect(page.locator('#sidebar.sidebar-collapsed')).toHaveCount(1);

  await page.locator('#sidebar-toggle').click();
  await expect(page.locator('#sidebar.sidebar-expanded')).toHaveCount(1);
  await settledBox(page, '#sidebar'); // the sidebar animates to its width: the handle is where it ends
  const handle = await page.locator('#sidebar-resizer').boundingBox();
  if (!handle) throw new Error('no resize handle');
  await page.mouse.move(handle.x + 2, 300);
  await page.mouse.down();
  await page.mouse.move(380, 300, { steps: 5 });
  await page.mouse.up();
  await expect
    .poll(async () => Math.round((await page.locator('#sidebar').boundingBox())?.width ?? 0))
    .toBe(380);
  await page.reload();
  await expect
    .poll(async () => Math.round((await page.locator('#sidebar').boundingBox())?.width ?? 0))
    .toBe(380);
});

test('the collapsed rail is one centred column with nothing clipped', async ({ page }) => {
  await mockData(page);
  await page.goto('/');
  await page.locator('#sidebar-toggle').click();
  await expect(page.locator('#sidebar.sidebar-collapsed')).toHaveCount(1);
  await settledBox(page, '#sidebar'); // the rail animates to its width
  const centre = async (selector: string) => {
    const box = await page.locator(selector).boundingBox();
    if (!box) throw new Error(`${selector} has no box`);
    return { cx: box.x + box.width / 2, x: box.x };
  };
  const logo = await centre('.sidebar-logo-icon');
  const toggle = await centre('#sidebar-toggle');
  const button = await centre('#new-chat-btn');
  expect(logo.x).toBeGreaterThanOrEqual(8);
  expect(Math.abs(logo.cx - button.cx)).toBeLessThanOrEqual(1);
  expect(Math.abs(toggle.cx - button.cx)).toBeLessThanOrEqual(1);
});

test('the Logs link moves the router without loading the page again', async ({ page }) => {
  await mockData(page);
  await page.goto('/');
  await page.evaluate(() => {
    (window as unknown as { __same: boolean }).__same = true;
  });
  await page.getByRole('link', { name: 'Logs' }).click();
  await expect(page).toHaveURL(/\/logs$/);
  expect(await page.evaluate(() => (window as unknown as { __same?: boolean }).__same)).toBe(true);
});

test('the workspace page wraps its header at 390px and has one Files section', async ({ page }) => {
  await mockData(page);
  await page.setViewportSize({ width: 390, height: 844 });
  await page.goto('/workspace/w1');
  await expect(page.getByRole('heading', { name: 'Research' })).toBeVisible();
  await expect(page.getByRole('heading', { name: 'Files' })).toHaveCount(1);
  await expect(page.getByText('1 chat', { exact: true })).toBeVisible();
  const button = await page
    .getByRole('button', { name: 'New chat in this workspace' })
    .boundingBox();
  expect((button?.x ?? 0) + (button?.width ?? 0)).toBeLessThanOrEqual(390);
  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth,
  );
  expect(overflow).toBe(0);
});

test('the icon picker fits a short window and scrolls', async ({ page }) => {
  await mockData(page);
  await page.setViewportSize({ width: 1280, height: 600 });
  await page.goto('/');
  await page.locator('.folder-header').first().click({ button: 'right' });
  await page.getByRole('menuitem', { name: 'Change icon' }).click();
  const dialog = page.locator('.modal-content');
  await expect(dialog).toBeVisible();
  const box = await settledBox(page, '.modal-content');
  expect((box?.y ?? -1) + (box?.height ?? 0)).toBeLessThanOrEqual(600);
  expect(
    await page.evaluate(() => {
      const g = document.querySelector('.icon-picker__grid');
      return (g?.scrollHeight ?? 0) > (g?.clientHeight ?? 0);
    }),
  ).toBe(true);
});
