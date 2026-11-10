import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';
import { readSse } from '../../../api/sse';
import { finishedFileChanges } from '../../../lib/fs-tools';
import { lastEvent, toTurns, turnReasoning, turnText, turnTools } from '../../../lib/chat-model';
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
    expect(turnText(t.steps)).toBe('Hello there, friend!');
    expect(turnReasoning(t.steps)).toBe('Planning a short greeting.');
    expect(t.model).toBe('Gemma4-26B-A4B-it-GGUF');
  });

  it('tools: call fragments merge and the result attaches', async () => {
    const t = await run('tools');
    expect(turnTools(t.steps)).toEqual([
      { id: 'call_1', name: 'grep_search', args: '{"query":"TODO"}', result: 'src/app.ts:3 TODO' },
    ]);
    expect(lastEvent(t.steps)).toBe('Searching the workspace');
    expect(t.steps.map((x) => x.kind)).toEqual(['text', 'tool', 'event', 'text']);
    expect(turnText(t.steps)).toBe('Let me look.\n\nFound one TODO in src/app.ts.');
  });

  it('files: a finished create_fs_file step and the multi-block reply', async () => {
    const t = await run('files');
    expect(finishedFileChanges(t.steps)).toBe(1);
    expect(turnTools(t.steps)[0]).toMatchObject({ name: 'create_fs_file', result: 'Created notes/hello.md' });
    expect(turnText(t.steps)).toContain('See [hello](notes/hello.md) for details.');
    expect(turnText(t.steps)).toContain('still code');
  });

  it('two rounds: reasoning, tool, text, reasoning, text stay separate steps', async () => {
    const t = await run('two-rounds');
    expect(t.steps.map((x) => x.kind)).toEqual(['reasoning', 'text', 'tool', 'reasoning', 'text']);
    expect(turnTools(t.steps)[0]?.result).toBe('3 files');
    expect(turnText(t.steps)).toBe('Checking.\n\nThere are 3 files.');
  });

  it('two rounds: the live steps equal the steps built from the stored rows of the same turn', async () => {
    const live = await run('two-rounds');
    const stored = toTurns([
      { id: 1, chat_id: 'c', role: 'user', content: 'how many files', parent_type: 'main' },
      {
        id: 2,
        chat_id: 'c',
        role: 'assistant',
        parent_type: 'main',
        reasoning_content: 'Need to list files.',
        content: 'Checking.',
        tool_calls: [{ id: 'call_1', function: { name: 'list_files', arguments: '{}' } }],
      },
      { id: 3, chat_id: 'c', role: 'tool', parent_type: 'main', tool_call_id: 'call_1', content: '3 files' },
      {
        id: 4,
        chat_id: 'c',
        role: 'assistant',
        parent_type: 'main',
        reasoning_content: 'Now answer.',
        content: 'There are 3 files.',
      },
    ] as never).at(-1);
    expect(stored?.kind === 'assistant' && stored.steps).toEqual(live.steps);
  });

  it('redact: rolls back the failed attempt', async () => {
    const t = await run('redact');
    expect(turnText(t.steps)).toBe('Draft one\n\nFixed answer.');
    expect(t.redactNotice).toBe('Correcting formatting...');
  });
});
