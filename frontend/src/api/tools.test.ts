import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from './client';
import { clarificationApi } from './tools';

afterEach(() => vi.unstubAllGlobals());

describe('clarificationApi.respond', () => {
  it('posts the answer with the callback and chat ids', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    await clarificationApi.respond('chat-1', 'call_1', 'Red');
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/tools/clarification/response');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({
      callback_id: 'call_1',
      chat_id: 'chat-1',
      type: 'answer',
      content: 'Red',
    });
  });

  it('rejects with the server message for an unknown or expired callback', async () => {
    const body = JSON.stringify({ error: 'Unknown or expired callback_id' });
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(body, { status: 404 })),
    );
    await expect(clarificationApi.respond('c', 'x', 'a')).rejects.toBeInstanceOf(ApiError);
    await expect(clarificationApi.respond('c', 'x', 'a')).rejects.toMatchObject({
      status: 404,
      message: 'Unknown or expired callback_id',
    });
  });
});
