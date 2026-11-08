import { describe, expect, it } from 'vitest';
import { router } from './routes';

describe('router', () => {
  const root = router.routes[0]!;
  const paths = (root.children ?? []).map((r) => r.path);

  it('registers the app routes under the root layout', () => {
    expect(paths).toEqual(expect.arrayContaining(['/', '/chat/:chatId', '/workspace/:workspaceId', '/logs']));
  });

  it('exposes the dev-only UI route only when the dev flag is on', () => {
    expect(paths.includes('/dev/ui')).toBe(import.meta.env.DEV);
  });

  it('has a catch-all route for unknown pages (F7)', () => {
    expect(paths).toContain('*');
  });
});
