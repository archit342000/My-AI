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
  firstMessageId,
  turnReasoning,
  turnText,
  turnTools,
  type Step,
} from './chat-model';
import {
  noToolReply,
  oneToolReply,
  subAgentReply,
  threeToolReply,
} from '../test/fixtures/chat-detail';

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
  it('pairs tool results with their calls into one assistant turn', () => {
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
    expect(turns.map((t) => t.kind)).toEqual(['user', 'assistant']);
    const assistant = turns[1];
    expect(assistant?.kind === 'assistant' && turnTools(assistant.steps)).toEqual([
      { id: 'call1', name: 'grep_search', args: '{}', result: 'a.txt' },
    ]);
    expect(assistant?.kind === 'assistant' && turnText(assistant.steps)).toBe('Let me check.\n\nDone.');
  });

  it('moves <think> text and reasoning into thinking and keeps the answer', () => {
    const turns = toTurns([msg({ id: '5', role: 'assistant', content: '<think>x</think>Answer', reasoning_content: 'why' })]);
    const t = turns[0];
    expect(t?.kind === 'assistant' && turnText(t.steps)).toBe('Answer');
    expect(t?.kind === 'assistant' && turnReasoning(t.steps)).toBe('why\nx');
  });

  it('skips sub-agent messages from the main transcript', () => {
    const turns = toTurns([msg({ id: '6', role: 'assistant', content: 'inner', parent_type: 'sub_agent' })]);
    expect(turns).toHaveLength(0);
  });
});

describe('parseToolCalls shapes', () => {
  const list = [{ id: 'x1', function: { name: 'read_file', arguments: '{"p":1}' } }];
  it('reads the list the API returns and the JSON string of older payloads', () => {
    expect(parseToolCalls(list)).toEqual([{ id: 'x1', name: 'read_file', args: '{"p":1}' }]);
    expect(parseToolCalls(JSON.stringify(list))).toEqual([{ id: 'x1', name: 'read_file', args: '{"p":1}' }]);
  });
  it('returns none for a non-list value', () => {
    expect(parseToolCalls({ id: 'x' })).toEqual([]);
  });
  it('skips null and non-object entries instead of throwing', () => {
    expect(parseToolCalls([null, 3, ...list])).toEqual([{ id: 'x1', name: 'read_file', args: '{"p":1}' }]);
  });
});

describe('toTurns with the real API shape', () => {
  const assistants = (m: Parameters<typeof toTurns>[0]) => toTurns(m).filter((t) => t.kind === 'assistant');

  it('makes one assistant turn for 0, 1 and 3 tool rounds', () => {
    expect(assistants(noToolReply)).toHaveLength(1);
    expect(assistants(oneToolReply)).toHaveLength(1);
    const three = toTurns(threeToolReply);
    expect(three.map((t) => t.kind)).toEqual(['user', 'assistant', 'user', 'assistant']);
  });

  it('shows stored tool calls and results from list-shaped tool_calls', () => {
    const [turn] = assistants(oneToolReply);
    expect(turn?.kind === 'assistant' && turnTools(turn.steps)).toEqual([
      { id: 't1', name: 'list_files', args: '{}', result: 'a.txt' },
    ]);
  });

  it('orders steps as reasoning, text, tool, then the next round', () => {
    const [turn] = assistants(oneToolReply);
    expect(turn?.kind === 'assistant' && turn.steps.map((s) => s.kind)).toEqual([
      'reasoning',
      'text',
      'tool',
      'text',
    ]);
  });

  it('lists every stored assistant row of the turn, first one first', () => {
    const turn = toTurns(threeToolReply)[1];
    expect(turn).toMatchObject({ id: '2', messageIds: ['2', '4', '6', '8'], model: 'M' });
    expect(turn?.kind === 'assistant' && turnTools(turn.steps).map((t) => t.result)).toEqual(['r1', 'r2', 'r3']);
  });

  it('shows stored tool calls from a JSON-string tool_calls row after reload', () => {
    const calls = JSON.stringify([{ id: 'j1', function: { name: 'read_file', arguments: '{}' } }]);
    const turn = toTurns([
      { ...oneToolReply[0]! },
      { ...oneToolReply[1]!, tool_calls: calls },
      { ...oneToolReply[2]!, tool_call_id: 'j1' },
    ]).at(-1);
    expect(turn?.kind === 'assistant' && turnTools(turn.steps)).toEqual([
      { id: 'j1', name: 'read_file', args: '{}', result: 'a.txt' },
    ]);
  });

  it('starts messageIds at a leading event row so Delete removes the whole turn', () => {
    const turn = toTurns([
      { ...oneToolReply[0]! },
      { ...oneToolReply[1]!, id: 20, role: 'event', content: 'planning', tool_calls: null },
      { ...oneToolReply[3]!, id: 21 },
    ]).at(-1);
    expect(turn).toMatchObject({ id: '20', messageIds: ['20', '21'] });
  });

  it('places a sub-agent row whose parent is not a tool call after the last tool step of its row', () => {
    const turn = toTurns([
      { ...subAgentReply[0]! },
      {
        ...subAgentReply[1]!,
        sub_agent_history: [
          { id: 30, agent_name: 'solo', role: 'assistant', content: 'solo says', parent_message_id: '2', sequence_order: 1 },
        ],
      },
    ]).at(-1);
    expect(turn?.kind === 'assistant' && turn.steps.map((s) => (s.kind === 'tool' ? s.id : `${s.kind}:${s.agent}`))).toEqual([
      's1',
      's2',
      'text:solo',
    ]);
  });

  it('firstMessageId is the first stored id of an assistant turn and the id of a user turn', () => {
    const [user, assistant] = toTurns(threeToolReply);
    expect(user && firstMessageId(user)).toBe('1');
    expect(assistant && firstMessageId(assistant)).toBe('2');
  });

  it('puts sub-agent steps after the tool that started them, and event rows in the steps', () => {
    const [turn] = assistants(subAgentReply);
    const label = (s: Step) => (s.kind === 'tool' ? `tool:${s.id}` : `${s.kind}:${s.agent ?? 'main'}`);
    expect(turn?.kind === 'assistant' && turn.steps.map(label)).toEqual([
      'tool:s1',
      'event:first',
      'text:first',
      'tool:s2',
      'text:second',
      'event:main',
      'text:main',
    ]);
    expect(turn?.kind === 'assistant' && turnText(turn.steps)).toBe('Summary.');
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

  it('reads a chat with three tool rounds as one assistant turn', () => {
    const turns = toTurns(threeToolChat.messages);
    expect(turns.filter((t) => t.kind === 'assistant')).toHaveLength(1);
  });

  it('keeps the tool calls the server returns as a list', () => {
    const tools = (messages: StoredMessage[]) =>
      toTurns(messages).flatMap((t) =>
        t.kind === 'assistant' ? t.steps.filter((step) => step.kind === 'tool') : [],
      );
    expect(tools(oneToolChat.messages)).toHaveLength(1);
    expect(tools(threeToolChat.messages)).toHaveLength(3);
  });
});
