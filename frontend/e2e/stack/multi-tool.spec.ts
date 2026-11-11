import { expect, test } from '@playwright/test';
import { botRows, send, startChat, waitIdle } from './helpers';

test('a reply with three tool rounds is one assistant row, live and after a reload', async ({
  page,
}) => {
  await page.goto('/');
  await send(page, 'MULTI use tools');
  await expect(page).toHaveURL(/\/chat\/[a-z0-9]+$/);
  // While it runs there is one live reply, never one row per tool round.
  await expect(page.locator('[data-live="true"]')).toHaveCount(1);
  await waitIdle(page);
  await expect(botRows(page)).toHaveCount(1);
  await expect(botRows(page).first()).toContainText('Final answer after 3 tool call(s).');
  await page.reload();
  await expect(botRows(page)).toHaveCount(1);
  await expect(botRows(page).first()).toContainText('Final answer after 3 tool call(s).');
});

test('the tool calls of the turn are kept after a reload', async ({ page }) => {
  await startChat(page, 'MULTI keep the tools');
  await page.reload();
  await expect(botRows(page)).toHaveCount(1);
  await botRows(page)
    .first()
    .getByRole('button', { name: /Thought process/ })
    .click();
  // All three calls are listed in the reply's box, each with its result.
  await expect(botRows(page).first().locator('.tool-item .activity-type')).toHaveText([
    'Get time',
    'Get time',
    'Get time',
  ]);
  await expect(botRows(page).first().locator('.tool-item .led.ok')).toHaveCount(3);
});
