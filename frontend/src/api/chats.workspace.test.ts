import { afterEach, describe, expect, it, vi } from 'vitest';
import { chatsApi } from './chats';

describe('chatsApi.createWorkspace', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('POSTs the name to /api/chats/workspaces and returns the created workspace', async () => {
    const fetchMock = vi.fn(async () =>
      new Response(JSON.stringify({ id: 'ws-1', name: 'Work' }), { status: 200, headers: { 'Content-Type': 'application/json' } }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const ws = await chatsApi.createWorkspace('Work');
    expect(ws).toEqual({ id: 'ws-1', name: 'Work' });
    const [path, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(path).toBe('/api/chats/workspaces');
    expect(init.method).toBe('POST');
    expect(JSON.parse(init.body as string)).toEqual({ name: 'Work' });
  });
});
