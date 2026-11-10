import { describe, expect, it } from 'vitest';
import type { StoredMessage } from '../api/types';
import { oneToolChat, plainChat, threeToolChat } from '../test/fixtures/api';
import {
  isAbsent,
  parseAttachments,
  parseToolCalls,
  parseUserContent,
  splitAttachmentNote,
  toTurns,
} from './chat-model';

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

describe('parseAttachments', () => {
  it('maps stored file references', () => {
    expect(parseAttachments([{ file_id: 'f1', name: 'a.txt', size: 3, mime_type: 'text/plain' }])).toEqual([
      { file_id: 'f1', name: 'a.txt', size: 3, mime_type: 'text/plain' },
    ]);
  });
  it('defaults missing size and type', () => {
    expect(parseAttachments([{ file_id: 'f1', name: 'a.txt' }])).toEqual([
      { file_id: 'f1', name: 'a.txt', size: 0, mime_type: '' },
    ]);
  });
  it('returns none for absent, non-array or malformed input', () => {
    expect(parseAttachments(null)).toEqual([]);
    expect(parseAttachments(undefined)).toEqual([]);
    expect(parseAttachments('nope')).toEqual([]);
    expect(parseAttachments([null, 3, { name: 'no id' }, { file_id: 'f1' }])).toEqual([]);
  });
});

describe('toTurns attachments', () => {
  it('puts stored attachments on user turns', () => {
    const turns = toTurns([
      msg({ id: '1', content: 'see file', attachments: [{ file_id: 'f1', name: 'a.txt', size: 3, mime_type: 'text/plain' }] }),
      msg({ id: '2', content: 'plain' }),
    ]);
    expect(turns[0]).toMatchObject({ kind: 'user', files: [{ file_id: 'f1', name: 'a.txt' }] });
    expect(turns[1]).toMatchObject({ kind: 'user', files: [] });
  });
});

const NOTE =
  '\n\n[System Note: The user has attached the following files. Use the `document_agent` tool with the provided file_id to read their contents if needed:\n- a.pdf (ID: f1)\n- my notes.txt (ID: f2)]';

describe('splitAttachmentNote', () => {
  it('strips the note and returns every file it lists, including the last (it ends with ])', () => {
    expect(splitAttachmentNote('read these' + NOTE)).toEqual({
      text: 'read these',
      noteFiles: [
        { file_id: 'f1', name: 'a.pdf', size: 0, mime_type: '' },
        { file_id: 'f2', name: 'my notes.txt', size: 0, mime_type: '' },
      ],
    });
  });
  it('strips a router-shaped note (it ends with ]) even when no entry parses', () => {
    const malformed =
      'hello\n\n[System Note: The user has attached the following files. Use it:\nnot an entry]';
    expect(splitAttachmentNote(malformed)).toEqual({ text: 'hello', noteFiles: [] });
  });
  it('leaves text that has the prefix but is not a router note (no closing ]) unchanged', () => {
    const typed = 'see\n\n[System Note: The user has attached the following files, I typed this';
    expect(splitAttachmentNote(typed)).toEqual({ text: typed, noteFiles: [] });
  });
  it('keeps the chip of a file whose name contains a newline', () => {
    const note =
      '\n\n[System Note: The user has attached the following files. Use it:\n- odd\nname.txt (ID: f9)\n- b.txt (ID: f10)]';
    const names = splitAttachmentNote('x' + note).noteFiles.map((f) => f.name);
    expect(names).toEqual(['odd\nname.txt', 'b.txt']);
  });
  it('returns text without a note unchanged', () => {
    expect(splitAttachmentNote('plain text')).toEqual({ text: 'plain text', noteFiles: [] });
  });
  it('leaves a user-typed System Note mention alone', () => {
    const typed = 'what is a [System Note: x] block?';
    expect(splitAttachmentNote(typed)).toEqual({ text: typed, noteFiles: [] });
  });
  it('only treats the last note block as the router note', () => {
    const typed = 'see\n\n[System Note: The user has attached the following files typed by me]';
    expect(splitAttachmentNote(typed + NOTE).text).toBe(typed);
  });
});

describe('toTurns with an attachment note', () => {
  it('uses the stored attachments for the chips and hides the note', () => {
    const turns = toTurns([
      msg({
        id: '1',
        content: 'read these' + NOTE,
        attachments: [{ file_id: 'f1', name: 'a.pdf', size: 9, mime_type: 'application/pdf' }],
      }),
    ]);
    expect(turns[0]).toMatchObject({
      kind: 'user',
      text: 'read these',
      files: [{ file_id: 'f1', name: 'a.pdf', size: 9 }],
    });
  });
  it('falls back to the files listed in the note for messages without stored attachments', () => {
    const turns = toTurns([msg({ id: '1', content: 'read these' + NOTE })]);
    expect(turns[0]).toMatchObject({ kind: 'user', text: 'read these' });
    const files = (turns[0] as { files: { name: string }[] }).files;
    expect(files.map((f) => f.name)).toEqual(['a.pdf', 'my notes.txt']);
  });
  it('strips the note from multimodal content with one text part (the router shape)', () => {
    const content = JSON.stringify([
      { type: 'text', text: 'look' + NOTE },
      { type: 'image_url', image_url: { url: 'data:image/png;base64,AAA' } },
    ]);
    const turns = toTurns([msg({ id: '1', content })]);
    expect(turns[0]).toMatchObject({
      kind: 'user',
      text: 'look',
      images: ['data:image/png;base64,AAA'],
    });
  });
});

describe('recorded chats from the real backend', () => {
  it('reads a plain chat as one user and one assistant turn', () => {
    const turns = toTurns(plainChat.messages);
    expect(turns.map((t) => t.kind)).toEqual(['user', 'assistant']);
  });

  // The turn-model change draws one row per user message; until it lands the stored tool rounds
  // (assistant, tool, assistant, ...) come out as several assistant turns, so these are expected to fail.
  it.fails('reads a chat with three tool rounds as one assistant turn', () => {
    const turns = toTurns(threeToolChat.messages);
    expect(turns.filter((t) => t.kind === 'assistant')).toHaveLength(1);
  });

  it.fails('keeps the tool calls the server returns as a list', () => {
    const tools = (messages: StoredMessage[]) =>
      toTurns(messages).flatMap((t) => (t.kind === 'assistant' ? t.tools : []));
    expect(tools(oneToolChat.messages)).toHaveLength(1);
    expect(tools(threeToolChat.messages)).toHaveLength(3);
  });
});
