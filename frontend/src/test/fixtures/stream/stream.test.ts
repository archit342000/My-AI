import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { readSse } from '../../../api/sse';
import { applyChunk, emptyLiveTurn, type LiveTurn, type StreamChunk } from '../../../features/chat/stream-reducer';

function load(name: string): ReadableStream<Uint8Array> {
  const text = readFileSync(resolve(__dirname, `${name}.sse`), 'utf8');
  const bytes = new TextEncoder().encode(text);
  return new ReadableStream({
    start(c) {
      // Deliver in small pieces to exercise line buffering across chunk boundaries.
      for (let i = 0; i < bytes.length; i += 17) c.enqueue(bytes.slice(i, i + 17));
      c.close();
    },
  });
}

async function run(name: string): Promise<LiveTurn> {
  let turn = emptyLiveTurn();
  for await (const raw of readSse(load(name))) turn = applyChunk(turn, raw as StreamChunk);
  return turn;
}

describe('recorded stream fixtures', () => {
  it('basic: content and reasoning accumulate', async () => {
    const t = await run('basic');
    expect(t.content).toBe('Hello there, friend!');
    expect(t.reasoning).toBe('Planning a short greeting.');
    expect(t.model).toBe('Gemma4-26B-A4B-it-GGUF');
  });

  it('tools: call fragments merge and the result attaches', async () => {
    const t = await run('tools');
    expect(t.tools).toEqual([
      { id: 'call_1', name: 'grep_search', args: '{"query":"TODO"}', result: 'src/app.ts:3 TODO' },
    ]);
    expect(t.events).toEqual(['Searching the workspace']);
    expect(t.content).toBe('Let me look.Found one TODO in src/app.ts.');
  });

  it('redact: rolls back the failed attempt', async () => {
    const t = await run('redact');
    expect(t.content).toBe('Draft one' + 'Fixed answer.');
    expect(t.redactNotice).toBe('Correcting formatting...');
  });
});
