import { afterEach, describe, expect, it, vi } from 'vitest';
import { meApi } from './me';

describe('meApi', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('reads the current user from /api/me', async () => {
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ id: 'u1', email: 'a@b.c', role: 'user' }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    vi.stubGlobal('fetch', fetchMock);
    await expect(meApi.get()).resolves.toEqual({ id: 'u1', email: 'a@b.c', role: 'user' });
    expect((fetchMock.mock.calls as unknown[][])[0]?.[0]).toBe('/api/me');
  });
});
