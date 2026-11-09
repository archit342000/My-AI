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
import { resumeTurn, sendTurn, stopTurn } from './send-turn';
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
  // The chat page loads the chat before sending, so the existing chat is in the cache.
  const queryClient = new QueryClient();
  queryClient.setQueryData(['chat', 'chat-1'], { id: 'chat-1', messages: [] });
  return {
    queryClient,
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

describe('send to an existing chat that is not cached (review fix)', () => {
  it('refuses with a toast instead of sending without the prior history', async () => {
    useToastStore.setState({ toasts: [] });
    useSettingsStore.setState({ model: 'M' } as never);
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    await sendTurn({ queryClient: new QueryClient(), chatId: 'uncached-existing', text: 'hi', files: [], isNewChat: false });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(useToastStore.getState().toasts.some((t) => t.type === 'error')).toBe(true);
    vi.unstubAllGlobals();
  });
});

describe('resumeTurn (Retry)', () => {
  it('posts to the resume URL without a pending user row and without messages', async () => {
    const seen: { pending?: unknown; body?: Record<string, unknown> } = {};
    const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
      if (path === '/api/chats/chat-1/resume') {
        seen.pending = useStreamStore.getState().pending;
        seen.body = JSON.parse(String(init?.body));
        return sseResponse(sseText([contentChunk('Again')], false));
      }
      return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    await resumeTurn(new QueryClient(), 'chat-1');
    expect(fetchMock.mock.calls.some(([p]) => p === '/api/chats/chat-1/resume')).toBe(true);
    expect(fetchMock.mock.calls.some(([p]) => p === '/v1/chat/completions')).toBe(false);
    expect(seen.pending).toBeNull();
    expect(seen.body).toMatchObject({ model: 'test-model', chatId: 'chat-1', messages: [] });
    expect(useStreamStore.getState().chatId).toBeNull();
  });

  it('shows an HTTP error as an interrupted turn plus a toast', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string) =>
        path === '/api/chats/chat-1/resume'
          ? new Response(JSON.stringify({ error: 'No user message found to resume from.' }), {
              status: 400,
              headers: { 'Content-Type': 'application/json' },
            })
          : new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
      ),
    );
    await resumeTurn(new QueryClient(), 'chat-1');
    expect(useStreamStore.getState().interrupted).toMatchObject({
      chatId: 'chat-1',
      kind: 'error',
      message: 'No user message found to resume from.',
    });
    expect(useToastStore.getState().toasts.some((t) => t.message === 'No user message found to resume from.')).toBe(true);
  });

  it('sends nothing while a stream is running or when no model is selected', async () => {
    const fetchMock = vi.fn(async () => new Response('{}', { status: 200 }));
    vi.stubGlobal('fetch', fetchMock);
    useStreamStore.setState({ chatId: 'other' });
    await resumeTurn(new QueryClient(), 'chat-1');
    expect(fetchMock).not.toHaveBeenCalled();

    useStreamStore.setState({ chatId: null });
    useSettingsStore.setState({ model: '' as never, modelName: '' as never });
    await resumeTurn(new QueryClient(), 'chat-1');
    expect(fetchMock).not.toHaveBeenCalled();
    expect(useToastStore.getState().toasts.some((t) => t.message === 'Select a model first')).toBe(true);
  });
});

describe('sendTurn when the server refuses the send (400)', () => {
  it('shows only a toast: no inline error row, nothing kept as interrupted', async () => {
    mockCompletion(
      () =>
        new Response(JSON.stringify({ error: 'a response is already in progress' }), {
          status: 400,
          headers: { 'Content-Type': 'application/json' },
        }),
    );
    await sendTurn(args());
    expect(useToastStore.getState().toasts.some((t) => t.message === 'a response is already in progress')).toBe(true);
    expect(useStreamStore.getState().interrupted).toBeNull();
    expect(useStreamStore.getState().chatId).toBeNull();
  });

  it('still keeps the partial reply for other failures (500)', async () => {
    mockCompletion(
      () => new Response(JSON.stringify({ error: 'boom' }), { status: 500, headers: { 'Content-Type': 'application/json' } }),
    );
    await sendTurn(args());
    expect(useStreamStore.getState().interrupted).toMatchObject({ kind: 'error', message: 'boom' });
  });
});
