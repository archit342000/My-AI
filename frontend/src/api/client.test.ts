import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError, apiJson, shouldRetryQuery } from './client';
import { useUserStore } from '../state/user-store';
import { useToastStore } from '../components/ui/toast-store';

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

describe('401 and 403 handling', () => {
  beforeEach(() => {
    useUserStore.setState({ sessionExpired: false });
    useToastStore.setState({ toasts: [] });
  });

  it('a 401 marks the session as expired and still throws', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'Unauthorized' }), { status: 401 })));
    await expect(apiJson('/api/x')).rejects.toMatchObject({ status: 401 });
    expect(useUserStore.getState().sessionExpired).toBe(true);
  });

  it('a 403 shows one toast per response and still throws an ApiError', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify({ error: 'Forbidden' }), { status: 403 })));
    await expect(apiJson('/api/x')).rejects.toBeInstanceOf(ApiError);
    const toasts = useToastStore.getState().toasts.filter((t) => t.message === "You don't have access to that.");
    expect(toasts).toHaveLength(1);
    expect(useUserStore.getState().sessionExpired).toBe(false);
  });

  it('other errors neither expire the session nor toast', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('{}', { status: 404 })));
    await expect(apiJson('/api/x')).rejects.toMatchObject({ status: 404 });
    expect(useUserStore.getState().sessionExpired).toBe(false);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });
});

describe('shouldRetryQuery', () => {
  it('retries a failure once, but never a 401 or 403', () => {
    expect(shouldRetryQuery(0, new Error('network'))).toBe(true);
    expect(shouldRetryQuery(1, new Error('network'))).toBe(false);
    expect(shouldRetryQuery(0, new ApiError(500, null, 'x'))).toBe(true);
    expect(shouldRetryQuery(0, new ApiError(401, null, 'x'))).toBe(false);
    expect(shouldRetryQuery(0, new ApiError(403, null, 'x'))).toBe(false);
  });
});

