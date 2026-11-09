import { afterEach, describe, expect, it, vi } from 'vitest';
import { resumeStream } from './completions';
import { contentChunk, sseResponse, sseText } from '../test/fixtures/sse';

afterEach(() => vi.unstubAllGlobals());

describe('resumeStream', () => {
  it('POSTs the body to the resume URL and yields the parsed chunks', async () => {
    const fetchMock = vi.fn(async () => sseResponse(sseText([contentChunk('Hi ')], false)));
    vi.stubGlobal('fetch', fetchMock);
    const chunks: unknown[] = [];
    for await (const chunk of resumeStream('chat 1', { model: 'm' }, new AbortController().signal)) chunks.push(chunk);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe('/api/chats/chat%201/resume');
    expect(init.method).toBe('POST');
    expect(JSON.parse(String(init.body))).toEqual({ model: 'm' });
    expect(JSON.stringify(chunks)).toContain('Hi ');
  });

  it('throws the server message on a non-2xx response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => new Response(JSON.stringify({ error: 'No user message found to resume from.' }), {
        status: 400,
        headers: { 'Content-Type': 'application/json' },
      })),
    );
    const run = async () => {
      for await (const chunk of resumeStream('c1', {}, new AbortController().signal)) void chunk;
    };
    await expect(run()).rejects.toThrow('No user message found to resume from.');
  });
});
