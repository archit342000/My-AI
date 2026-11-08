/**
 * Builders for recorded completion streams. Tests hand these to a mocked `fetch` so streaming UI
 * (stop, error, retry, tool cards) runs without touching the inference server. The same chunk
 * shapes are what `/v1/chat/completions` sends as `data:` lines.
 */

export type Chunk = Record<string, unknown>;

/** A content delta, optionally with a model name. */
export function contentChunk(content: string, model = 'test-model'): Chunk {
  return { choices: [{ delta: { content } }], model };
}

/** A reasoning delta. */
export function reasoningChunk(reasoning_content: string, model = 'test-model'): Chunk {
  return { choices: [{ delta: { reasoning_content } }], model };
}

/** An app event delta (`role: 'event'`), e.g. "Searching the web". */
export function eventChunk(content: string): Chunk {
  return { choices: [{ delta: { role: 'event', content } }] };
}

/** A tool call announcement, followed later by its result. */
export function toolCallChunk(id: string, name: string, args: string): Chunk {
  return {
    choices: [{ delta: { tool_calls: [{ index: 0, id, function: { name, arguments: args } }] } }],
  };
}

export function toolResultChunk(id: string, result: string): Chunk {
  return { choices: [{ delta: { tool_result: { tool_call_id: id, content: result } } }] };
}

/** An error the server reports mid-stream. */
export function errorChunk(message: string): Chunk {
  return { error: message };
}

/** Serialises chunks as an SSE body. `done` appends the `[DONE]` sentinel unless it is false. */
export function sseText(chunks: Chunk[], done = true): string {
  const lines = chunks.map((c) => `data: ${JSON.stringify(c)}\n\n`);
  return done ? [...lines, 'data: [DONE]\n\n'].join('') : lines.join('');
}

/** A Response whose body delivers the SSE text in small pieces (exercises line buffering). */
export function sseResponse(text: string, pieceSize = 23): Response {
  const bytes = new TextEncoder().encode(text);
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (let i = 0; i < bytes.length; i += pieceSize) controller.enqueue(bytes.slice(i, i + pieceSize));
      controller.close();
    },
  });
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}

/**
 * A Response that stays open after the given chunks and errors with AbortError when the request
 * signal aborts, the way a real fetch body does when the user presses Stop.
 */
export function abortableSseResponse(chunks: Chunk[], signal: AbortSignal): Response {
  const encoder = new TextEncoder();
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(`data: ${JSON.stringify(c)}\n\n`));
      signal.addEventListener('abort', () => {
        controller.error(new DOMException('The operation was aborted.', 'AbortError'));
      });
    },
  });
  return new Response(body, { status: 200, headers: { 'Content-Type': 'text/event-stream' } });
}
