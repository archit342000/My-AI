import { QueryClient } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useSettingsStore } from '../../state/settings-store';
import { useStreamStore } from '../../state/stream-store';
import {
  abortableSseResponse,
  contentChunk,
  errorChunk,
  sseResponse,
  sseText,
  toolCallChunk,
  toolResultChunk,
} from '../../test/fixtures/sse';
import { sendTurn, stopTurn } from './send-turn';
import { useToastStore } from '../../components/ui/toast-store';

/** Routes only the completion endpoint; every other request gets an empty JSON response. */
function mockCompletion(respond: (signal: AbortSignal) => Response, seen: { pending?: unknown } = {}) {
  const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
    if (path === '/v1/chat/completions') {
      seen.pending = useStreamStore.getState().pending;
      return respond(init?.signal ?? new AbortController().signal);
    }
    return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
  });
  vi.stubGlobal('fetch', fetchMock);
  return fetchMock;
}

function args(overrides: Partial<Parameters<typeof sendTurn>[0]> = {}) {
  return {
    queryClient: new QueryClient(),
    chatId: 'chat-1',
    text: 'hello',
    files: [],
    isNewChat: false,
    ...overrides,
  };
}

beforeEach(() => {
  useSettingsStore.setState({ model: 'test-model', modelName: 'test-model' });
  useStreamStore.setState({
    chatId: null,
    live: null,
    pending: null,
    interrupted: null,
    controller: null,
  });
  useToastStore.setState({ toasts: [] });
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('sendTurn with a stream error (F-14)', () => {
  it('keeps the partial reply and records the error instead of dropping the turn', async () => {
    mockCompletion(() =>
      sseResponse(sseText([contentChunk('Partial '), errorChunk('Upstream timed out')], false)),
    );
    await sendTurn(args());
    const { interrupted, chatId } = useStreamStore.getState();
    expect(chatId).toBeNull();
    expect(interrupted).toMatchObject({
      chatId: 'chat-1',
      kind: 'error',
      message: 'Upstream timed out',
      live: { content: 'Partial ' },
    });
    expect(useToastStore.getState().toasts.some((t) => t.message === 'Upstream timed out')).toBe(true);
  });
});

describe('stop (F-15)', () => {
  it('keeps what arrived before Stop, marked as stopped', async () => {
    const chunks = [contentChunk('Half of ')];
    mockCompletion((signal) => abortableSseResponse(chunks, signal));
    const sent = sendTurn(args());
    // Abort once the first chunk has been applied.
    await vi.waitFor(() => expect(useStreamStore.getState().live?.content).toBe('Half of '));
    await stopTurn();
    await sent;
    expect(useStreamStore.getState().chatId).toBeNull();
    expect(useStreamStore.getState().interrupted).toMatchObject({
      chatId: 'chat-1',
      kind: 'stopped',
      live: { content: 'Half of ' },
    });
  });
});

describe('retry does not duplicate the user row (F-16)', () => {
  it('streams without an optimistic pending user when the turn already exists', async () => {
    const seen: { pending?: unknown } = {};
    mockCompletion(() => sseResponse(sseText([contentChunk('Again')])), seen);
    await sendTurn(args({ userTurnExists: true }));
    expect(seen.pending).toBeNull();
    expect(useStreamStore.getState().interrupted).toBeNull();
  });

  it('regenerate sends the edited turn once, after the history that precedes it', async () => {
    const bodies: Array<{ messages: Array<{ role: string; content: string }> }> = [];
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string, init?: RequestInit) => {
        if (path === '/v1/chat/completions') {
          bodies.push(JSON.parse(String(init?.body)));
          return sseResponse(sseText([contentChunk('Again')]));
        }
        return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
      }),
    );
    await sendTurn(
      args({
        userTurnExists: true,
        history: [
          { role: 'user', content: 'earlier question' },
          { role: 'assistant', content: 'earlier answer' },
        ],
      }),
    );
    const messages = bodies[0]!.messages;
    expect(messages.map((m) => m.content)).toEqual(['earlier question', 'earlier answer', 'hello']);
    expect(messages.filter((m) => m.content === 'hello')).toHaveLength(1);
  });

  it('shows the optimistic user row for a new message', async () => {
    const seen: { pending?: unknown } = {};
    mockCompletion(() => sseResponse(sseText([contentChunk('Hi')])), seen);
    await sendTurn(args());
    expect(seen.pending).toMatchObject({ text: 'hello' });
  });
});

describe('tool activity in a stream', () => {
  it('shows a call as running, then attaches its result on the live turn', async () => {
    mockCompletion(() =>
      sseResponse(
        sseText(
          [
            toolCallChunk('call_1', 'grep_search', '{"query":"TODO"}'),
            toolResultChunk('call_1', 'src/app.ts:3 TODO'),
            contentChunk('Found one.'),
          ],
          false,
        ),
      ),
    );
    const snapshots: Array<Array<{ result: string | null }>> = [];
    const unsubscribe = useStreamStore.subscribe((s) => {
      if (s.live && s.live.tools.length > 0) snapshots.push(s.live.tools);
    });
    await sendTurn(args());
    unsubscribe();
    expect(snapshots[0]?.[0]?.result).toBeNull();
    expect(snapshots.at(-1)).toEqual([
      { id: 'call_1', name: 'grep_search', args: '{"query":"TODO"}', result: 'src/app.ts:3 TODO' },
    ]);
  });
});
