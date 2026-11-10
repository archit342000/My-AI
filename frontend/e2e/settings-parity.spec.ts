import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';

import { expect, test, type Page } from '@playwright/test';

// The settings and chat endpoints are answered in the browser, so the spec needs only the frontend
// (the real /api/me answers as the admin under the static auth provider).
const basic = readFileSync(
  fileURLToPath(new URL('../src/test/fixtures/stream/basic.sse', import.meta.url)),
  'utf8',
);

/** Opens the settings page at System, from the navigation panel. */
async function openSystemSettings(page: Page) {
  await page.getByRole('button', { name: 'System', exact: true }).click();
  await expect(page.getByRole('region', { name: 'Settings' })).toBeVisible();
}

test('Settings is a page with Back, not a pop-up, and System opens the same page at its part', async ({
  page,
}) => {
  await page.goto('/');
  await page.getByRole('button', { name: 'Settings', exact: true }).click();
  const settings = page.getByRole('region', { name: 'Settings' });
  await expect(settings).toBeVisible();
  await expect(page).toHaveURL(/\?settings=chat$/);
  await expect(page.getByRole('dialog')).toHaveCount(0);
  const parts = page.getByRole('navigation', { name: 'Settings sections' });
  await expect(parts.getByRole('button')).toHaveText([
    'Chat',
    'Models',
    'Personas',
    'Skills',
    'Memory',
    'Agents',
    'System',
  ]);
  await settings.getByRole('button', { name: 'Back' }).click();
  await expect(settings).toHaveCount(0);
  await expect(page).toHaveURL(/\/$/);

  await openSystemSettings(page);
  await expect(page).toHaveURL(/\?settings=system$/);
  await expect(parts.getByRole('button', { name: 'System' })).toHaveAttribute(
    'aria-current',
    'true',
  );
  await expect(settings.getByRole('heading', { name: 'System', exact: true })).toBeInViewport();
  // The list follows the scrolling, and a part can be reached from it.
  await parts.getByRole('button', { name: 'Personas' }).click();
  await expect(settings.getByRole('heading', { name: 'Personas', exact: true })).toBeInViewport();
  await expect(parts.getByRole('button', { name: 'Personas' })).toHaveAttribute(
    'aria-current',
    'true',
  );
  // Scrolling by hand moves the highlight too.
  await settings.locator('.set-content').evaluate((el) => (el.scrollTop = 0));
  await expect(parts.getByRole('button', { name: 'Chat' })).toHaveAttribute('aria-current', 'true');
  await page.goBack();
  await expect(settings).toHaveCount(0);
});

test('a setting is kept the moment it changes and the page says Saved', async ({ page }) => {
  await page.goto('/');
  await openSystemSettings(page);
  const settings = page.getByRole('region', { name: 'Settings' });
  await expect(settings.locator('.set-saved')).toHaveCount(0);
  await settings
    .getByRole('radiogroup', { name: 'Panels' })
    .getByRole('radio', { name: 'Solid' })
    .click();
  await expect(settings.locator('.set-saved')).toHaveText('Saved');
  await expect(page.locator('html')).toHaveAttribute('data-glass', 'solid');
  await page.reload();
  await expect(page.locator('html')).toHaveAttribute('data-glass', 'solid');
  await expect(
    page.getByRole('radiogroup', { name: 'Panels' }).getByRole('radio', { name: 'Solid' }),
  ).toHaveAttribute('aria-checked', 'true');
});

test.beforeEach(async ({ page }) => {
  await page.addInitScript(() => {
    localStorage.setItem('my_ai_selected_model', 'Gemma4-26B-A4B-it-GGUF');
    localStorage.setItem('my_ai_selected_model_name', 'Gemma4-26B-A4B-it-GGUF');
  });
});

test('delete all chats asks first, empties the list and lands on an empty home page', async ({
  page,
}) => {
  let chats = [
    { id: 'c1', title: 'First chat', timestamp: 1, workspace_id: null },
    { id: 'c2', title: 'Second chat', timestamp: 2, workspace_id: null },
  ];
  let deleted = 0;
  await page.route(/\/api\/chats$/, (route) => {
    if (route.request().method() === 'DELETE') {
      deleted += 1;
      chats = [];
      return route.fulfill({ json: {} });
    }
    return route.request().method() === 'GET' ? route.fulfill({ json: chats }) : route.fallback();
  });
  await page.goto('/');
  await expect(page.getByText('First chat')).toBeVisible();
  await openSystemSettings(page);
  await page.getByRole('button', { name: 'Delete all', exact: true }).click();
  expect(deleted).toBe(0); // nothing is deleted before the confirmation
  await page
    .getByRole('dialog', { name: 'Delete all chats?' })
    .getByRole('button', { name: 'Delete all chats' })
    .click();
  await expect(page.getByText('First chat')).toHaveCount(0);
  await expect(page.getByText('Second chat')).toHaveCount(0);
  await expect(page).toHaveURL(/\/$/);
  await expect(page.locator('#welcome-hero')).toBeVisible();
  expect(deleted).toBe(1);
});

test('an admin saves a GitHub token (status only) and chooses allowed git commands', async ({
  page,
}) => {
  let configured = false;
  let allowed = ['status'];
  const posts: Array<Record<string, unknown>> = [];
  await page.route('**/api/tools/config/settings', async (route) => {
    if (route.request().method() === 'POST') {
      const body = route.request().postDataJSON() as Record<string, unknown>;
      posts.push(body);
      if (typeof body.github_pat === 'string') configured = true;
      if (Array.isArray(body.git_allowed_commands)) allowed = body.git_allowed_commands as string[];
      return route.fulfill({ json: {} });
    }
    return route.fulfill({
      json: {
        code_runner_timeout: 30,
        code_runner_memory_limit: '512M',
        code_runner_cpu_limit: '1.0',
        code_runner_max_output_size: 65536,
        github_pat_configured: configured,
        git_known_commands: ['status', 'diff', 'commit'],
        git_allowed_commands: allowed,
      },
    });
  });
  await page.goto('/');
  await openSystemSettings(page);
  await expect(page.getByText(/^None set\./)).toBeVisible();
  const field = page.getByLabel('GitHub token');
  await field.fill('ghp_secret_value');
  await page.getByRole('button', { name: 'Save token' }).click();
  await expect(page.getByText('Token saved')).toBeVisible();
  await expect(field).toHaveValue('');
  await expect(page.getByText(/^One is set\./)).toBeVisible();
  // the token is sent once and never shown again
  expect(posts.filter((p) => 'github_pat' in p)).toHaveLength(1);
  await expect(page.locator('body')).not.toContainText('ghp_secret_value');
  await page.getByRole('checkbox', { name: 'diff' }).check();
  await expect.poll(() => allowed).toEqual(['status', 'diff']);
});

test('a thinking profile set in Settings away from a chat is what the next new chat starts with', async ({
  page,
}) => {
  const bodies: Array<Record<string, unknown>> = [];
  await page.route('**/v1/chat/completions', (route) => {
    bodies.push(route.request().postDataJSON() as Record<string, unknown>);
    return route.fulfill({ status: 200, contentType: 'text/event-stream', body: basic });
  });
  await page.goto('/');
  await openSystemSettings(page);
  await page
    .getByRole('radiogroup', { name: 'Thinking profile' })
    .getByRole('radio', { name: 'None' })
    .click();
  await page.keyboard.press('Escape');
  await expect(page.getByRole('region', { name: 'Settings' })).toHaveCount(0);
  await page.getByRole('button', { name: 'New chat' }).click();
  await page.locator('#chat-textarea').fill('hello');
  await page.keyboard.press('Enter');
  await expect.poll(() => bodies.length).toBeGreaterThan(0);
  expect(bodies[0]).toMatchObject({ thinking_profile: 'none', enable_thinking: false });
});

test('the memory list can be searched, filtered by tag and sorted', async ({ page }) => {
  await page.route('**/api/tools/preferences', (route) =>
    route.fulfill({
      json: {
        preferences: [
          { id: 'a', content: 'Answer in British English', tag: 'preference', timestamp: 100 },
          { id: 'b', content: 'The project is called Atlas', tag: 'project', timestamp: 300 },
          { id: 'c', content: 'Use metric units', tag: 'preference', timestamp: 200 },
        ],
      },
    }),
  );
  await page.goto('/');
  await openSystemSettings(page);
  const titles = page.locator('#settings-memory .crud-title__name');
  await expect(titles).toHaveText([
    'The project is called Atlas',
    'Use metric units',
    'Answer in British English',
  ]);
  await page.getByLabel('Search memory').fill('atlas');
  await expect(titles).toHaveText(['The project is called Atlas']);
  await page.getByLabel('Search memory').fill('');
  await page.getByRole('combobox', { name: 'Order' }).click();
  await page.getByRole('option', { name: 'Oldest first' }).click();
  await expect(titles.first()).toHaveText('Answer in British English');
  await page.getByRole('combobox', { name: 'Filter by tag' }).click();
  await page.getByRole('option', { name: 'Project' }).click();
  await expect(titles).toHaveText(['The project is called Atlas']);
});
