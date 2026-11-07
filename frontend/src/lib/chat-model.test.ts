import { describe, expect, it } from 'vitest';
import type { StoredMessage } from '../api/types';
import { isAbsent, parseToolCalls, parseUserContent, toTurns } from './chat-model';

function msg(over: Partial<StoredMessage>): StoredMessage {
  return {
    id: '1',
    chat_id: 'c',
    role: 'user',
    content: '',
    timestamp: null,
    model: null,
    tool_calls: null,
    tool_call_id: null,
    name: null,
    parent_id: null,
    parent_type: 'main',
    reasoning_content: null,
    ...over,
  };
}

describe('isAbsent', () => {
  it('treats null, empty and the string "None" as absent', () => {
    expect(isAbsent(null)).toBe(true);
    expect(isAbsent('None')).toBe(true);
    expect(isAbsent('')).toBe(true);
    expect(isAbsent('hi')).toBe(false);
  });
});

describe('parseUserContent', () => {
  it('reads plain text', () => {
    expect(parseUserContent('hello')).toEqual({ text: 'hello', images: [] });
  });
  it('reads multimodal JSON parts', () => {
    const raw = JSON.stringify([
      { type: 'text', text: 'look' },
      { type: 'image_url', image_url: { url: 'data:image/png;base64,AAA' } },
    ]);
    expect(parseUserContent(raw)).toEqual({ text: 'look', images: ['data:image/png;base64,AAA'] });
  });
  it('falls back to text for invalid JSON', () => {
    expect(parseUserContent('[not json')).toEqual({ text: '[not json', images: [] });
  });
});

describe('parseToolCalls', () => {
  it('extracts id, name and arguments', () => {
    const raw = JSON.stringify([{ id: 'x1', type: 'function', function: { name: 'read_file', arguments: '{"p":1}' } }]);
    expect(parseToolCalls(raw)).toEqual([{ id: 'x1', name: 'read_file', args: '{"p":1}' }]);
  });
  it('returns none for absent or broken input', () => {
    expect(parseToolCalls('None')).toEqual([]);
    expect(parseToolCalls('{bad')).toEqual([]);
  });
});

describe('toTurns', () => {
  it('pairs tool results with their calls and drops tool-role rows', () => {
    const messages: StoredMessage[] = [
      msg({ id: '1', role: 'user', content: 'list files' }),
      msg({
        id: '2',
        role: 'assistant',
        content: 'Let me check.',
        model: 'm1',
        tool_calls: JSON.stringify([{ id: 'call1', function: { name: 'grep_search', arguments: '{}' } }]),
      }),
      msg({ id: '3', role: 'tool', tool_call_id: 'call1', content: 'a.txt' }),
      msg({ id: '4', role: 'assistant', content: 'Done.' }),
    ];
    const turns = toTurns(messages);
    expect(turns.map((t) => t.kind)).toEqual(['user', 'assistant', 'assistant']);
    const assistant = turns[1];
    expect(assistant?.kind === 'assistant' && assistant.tools).toEqual([
      { id: 'call1', name: 'grep_search', args: '{}', result: 'a.txt' },
    ]);
  });

  it('moves <think> text and reasoning into thinking and keeps the answer', () => {
    const turns = toTurns([msg({ id: '5', role: 'assistant', content: '<think>x</think>Answer', reasoning_content: 'why' })]);
    expect(turns[0]).toMatchObject({ kind: 'assistant', text: 'Answer', thinking: 'why\nx' });
  });

  it('skips sub-agent messages from the main transcript', () => {
    const turns = toTurns([msg({ id: '6', role: 'assistant', content: 'inner', parent_type: 'sub_agent' })]);
    expect(turns).toHaveLength(0);
  });
});
