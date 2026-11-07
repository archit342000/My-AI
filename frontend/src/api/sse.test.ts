import { describe, expect, it } from 'vitest';
import { parseSseLine, readSse } from './sse';

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const enc = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(enc.encode(c));
      controller.close();
    },
  });
}

describe('parseSseLine', () => {
  it('ignores blank and non-data lines', () => {
    expect(parseSseLine('')).toBeNull();
    expect(parseSseLine('event: x')).toBeNull();
  });
  it('parses data JSON', () => {
    expect(parseSseLine('data: {"a":1}')).toEqual({ done: false, value: { a: 1 } });
  });
  it('detects [DONE]', () => {
    expect(parseSseLine('data: [DONE]')).toEqual({ done: true });
  });
});

describe('readSse', () => {
  it('joins lines split across chunks and stops at [DONE]', async () => {
    const body = streamOf(['data: {"x":', '1}\n\ndata: {"x":2}\n', 'data: [DONE]\n', 'data: {"x":3}\n']);
    const out: unknown[] = [];
    for await (const ev of readSse(body)) out.push(ev);
    expect(out).toEqual([{ x: 1 }, { x: 2 }]);
  });

  it('yields a trailing event without a newline', async () => {
    const out: unknown[] = [];
    for await (const ev of readSse(streamOf(['data: {"y":true}']))) out.push(ev);
    expect(out).toEqual([{ y: true }]);
  });
});
