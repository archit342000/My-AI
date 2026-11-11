import { afterEach, describe, expect, it, vi } from 'vitest';
import { buildCompletionBody, resumeStream, type CompletionOptions } from './completions';
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


describe('buildCompletionBody temporary flag', () => {
  const base: CompletionOptions = {
    model: 'm',
    modelName: 'M',
    messages: [],
    chatId: 'c1',
    sampling: {} as CompletionOptions['sampling'],
    modes: {
      researchMode: false,
      userPreferences: false,
      visionEnabled: false,
      fileSystemMode: false,
      browsingMode: false,
      gitMode: false,
      codeExecutionMode: false,
    },
    personaId: null,
    folder: null,
  };

  it('sends temporary: true only for a temporary chat', () => {
    expect(buildCompletionBody({ ...base, temporary: true }).temporary).toBe(true);
    expect(JSON.parse(JSON.stringify(buildCompletionBody(base)))).not.toHaveProperty('temporary');
    expect(JSON.parse(JSON.stringify(buildCompletionBody({ ...base, temporary: false })))).not.toHaveProperty('temporary');
  });
});
