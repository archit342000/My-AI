import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiJson } from './client';

afterEach(() => vi.restoreAllMocks());

describe('apiJson', () => {
  it('sends JSON bodies with a content type and parses the response', async () => {
    const fetchMock = vi.fn(async () => new Response(JSON.stringify({ ok: true }), { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    const out = await apiJson<{ ok: boolean }>('/api/x', { method: 'POST', json: { a: 1 } });
    expect(out).toEqual({ ok: true });
    const [, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(new Headers(init.headers).get('Content-Type')).toBe('application/json');
    expect(init.body).toBe('{"a":1}');
  });

  it('throws ApiError with status and the server error message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'nope' }), { status: 404 })));
    await expect(apiJson('/api/missing')).rejects.toMatchObject({ status: 404, message: 'nope' });
    await expect(apiJson('/api/missing')).rejects.toBeInstanceOf(ApiError);
  });

  it('falls back to the status line when the error body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>', { status: 500, statusText: 'Boom' })));
    await expect(apiJson('/api/x')).rejects.toMatchObject({ status: 500, message: '500 Boom' });
  });
});
