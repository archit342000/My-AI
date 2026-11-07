/**
 * Reads a `text/event-stream`-style body (lines of `data: <json>`) as an async iterator.
 * `data: [DONE]` ends the stream. Blank lines and non-data lines are skipped.
 * Parsing is pure: `parseSseLines` is exported for unit tests.
 */

export function parseSseLine(line: string): { done: true } | { done: false; value: unknown } | null {
  const trimmed = line.trim();
  if (!trimmed || !trimmed.startsWith('data: ')) return null;
  const payload = trimmed.slice(6);
  if (payload === '[DONE]') return { done: true };
  return { done: false, value: JSON.parse(payload) as unknown };
}

export async function* readSse(body: ReadableStream<Uint8Array>): AsyncGenerator<unknown> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  try {
    for (;;) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() ?? '';
      for (const line of lines) {
        const parsed = parseSseLine(line);
        if (!parsed) continue;
        if (parsed.done) return;
        yield parsed.value;
      }
    }
    buffer += decoder.decode();
    const parsed = parseSseLine(buffer);
    if (parsed && !parsed.done) yield parsed.value;
  } finally {
    reader.releaseLock();
  }
}
