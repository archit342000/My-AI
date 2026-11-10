import { expect, test } from '@playwright/test';
import { botRows, send, startChat, waitIdle } from './helpers';

// Fixed by the turn-model change (one assistant turn per user message): until it is merged these two fail, and
// `test.fail()` keeps the suite green. When it lands Playwright reports the unexpected pass: delete the marker.
test('a reply with three tool rounds is one assistant row, live and after a reload', async ({
  page,
}) => {
  test.fail(true, 'develop draws one row per assistant message: fixed by the turn-model change');
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
  test.fail(true, 'develop draws one row per assistant message: fixed by the turn-model change');
  await startChat(page, 'MULTI keep the tools');
  await page.reload();
  await expect(botRows(page)).toHaveCount(1);
  await botRows(page).first().locator('.thought-header').click();
  // All three calls are listed under the reply.
  await expect(botRows(page).first().getByText('Get Time')).toHaveCount(3);
});
