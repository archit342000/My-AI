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
import { BUSY_TOAST, historyFromCache, resumeTurn, sendTurn, stopTurn } from './send-turn';
import { turnText, turnTools } from '../../lib/chat-model';
import { threeToolReply } from '../../test/fixtures/chat-detail';
import { useToastStore } from '../../components/ui/toast-store';
import { queryKeys } from '../../api/chats';
import { artifactsKey } from '../../api/filesystem';
import { useUiStore } from '../../state/ui-store';

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
      live: { steps: [{ kind: 'text', text: 'Partial ', agent: null }] },
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
    await vi.waitFor(() => expect(turnText(useStreamStore.getState().live?.steps ?? [])).toBe('Half of '));
    await stopTurn();
    await sent;
    expect(useStreamStore.getState().chatId).toBeNull();
    expect(useStreamStore.getState().interrupted).toMatchObject({
      chatId: 'chat-1',
      kind: 'stopped',
      live: { steps: [{ kind: 'text', text: 'Half of ', agent: null }] },
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
      const tools = s.live ? turnTools(s.live.steps) : [];
      if (tools.length > 0) snapshots.push(tools);
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

  it('shows the turn-in-progress refusal as a toast only, no inline error row', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string) =>
        path === '/api/chats/chat-1/resume'
          ? new Response(JSON.stringify({ error: 'a response is already in progress' }), {
              status: 400,
              headers: { 'Content-Type': 'application/json' },
            })
          : new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
      ),
    );
    await resumeTurn(new QueryClient(), 'chat-1');
    const messages = useToastStore.getState().toasts.map((t) => t.message);
    expect(messages).toContain('a response is already in progress');
    expect(useStreamStore.getState().interrupted).toBeNull();
    expect(useStreamStore.getState().chatId).toBeNull();
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

describe('a turn refused for being over the rate limit (429)', () => {
  const limited = () =>
    new Response(JSON.stringify({ error: 'Too many requests; try again shortly.' }), {
      status: 429,
      headers: { 'Content-Type': 'application/json', 'Retry-After': '30' },
    });

  it('shows only a toast on a send: no inline error row, nothing kept as interrupted', async () => {
    mockCompletion(limited);
    await sendTurn(args());
    expect(useToastStore.getState().toasts.some((t) => t.message === 'Too many requests; try again shortly.')).toBe(true);
    expect(useStreamStore.getState().interrupted).toBeNull();
    expect(useStreamStore.getState().chatId).toBeNull();
  });

  it('shows only a toast on Retry (resume) too', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string) =>
        path === '/api/chats/chat-1/resume' ? limited() : new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
      ),
    );
    await resumeTurn(new QueryClient(), 'chat-1');
    expect(useToastStore.getState().toasts.some((t) => t.message === 'Too many requests; try again shortly.')).toBe(true);
    expect(useStreamStore.getState().interrupted).toBeNull();
  });
});

describe('sidebar chat list during a turn', () => {
  it('is refreshed once the send is accepted (first chunk), not only after the stream ends', async () => {
    mockCompletion(() => sseResponse(sseText([contentChunk('A'), contentChunk('B')], false)));
    const a = args();
    const seen: Array<string | undefined> = [];
    const original = a.queryClient.invalidateQueries.bind(a.queryClient);
    vi.spyOn(a.queryClient, 'invalidateQueries').mockImplementation((filters) => {
      if (JSON.stringify(filters?.queryKey) === JSON.stringify(queryKeys.chats)) {
        seen.push(turnText(useStreamStore.getState().live?.steps ?? []));
      }
      return original(filters);
    });
    await sendTurn(a);
    // The first refresh happens before the reply has been applied, the last one after finish()
    // has cleared the live turn.
    expect(seen.length).toBeGreaterThanOrEqual(2);
    expect(seen[0]).not.toBe('AB');
    expect(seen[seen.length - 1]).toBe('');
  });

  it('keeps the turn open until the chat refetch has resolved, then ends it', async () => {
    mockCompletion(() => sseResponse(sseText([contentChunk('A')], false)));
    const a = args();
    const original = a.queryClient.invalidateQueries.bind(a.queryClient);
    const afterChatRefetch: boolean[] = [];
    vi.spyOn(a.queryClient, 'invalidateQueries').mockImplementation(async (filters) => {
      const result = await original(filters);
      if (JSON.stringify(filters?.queryKey) === JSON.stringify(queryKeys.chat('chat-1'))) {
        // Checked right after the refetch resolved: finish() has not run yet.
        afterChatRefetch.push(useStreamStore.getState().chatId !== null);
      }
      return result;
    });
    await sendTurn(a);
    expect(afterChatRefetch.at(-1)).toBe(true);
    expect(useStreamStore.getState().chatId).toBeNull();
  });

  it('ends the turn as soon as the chat is refetched, before the sidebar list refresh', async () => {
    mockCompletion(() => sseResponse(sseText([contentChunk('A')], false)));
    const a = args();
    const original = a.queryClient.invalidateQueries.bind(a.queryClient);
    const streamingAtListRefresh: boolean[] = [];
    vi.spyOn(a.queryClient, 'invalidateQueries').mockImplementation((filters) => {
      if (JSON.stringify(filters?.queryKey) === JSON.stringify(queryKeys.chats)) {
        streamingAtListRefresh.push(useStreamStore.getState().chatId !== null);
      }
      return original(filters);
    });
    await sendTurn(a);
    // The first refresh is the accepted-send one (still streaming); the last is after finish().
    expect(streamingAtListRefresh.at(-1)).toBe(false);
  });
});

describe('historyFromCache', () => {
  it('returns one assistant entry per turn, built from its text steps', () => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(queryKeys.chat('c1'), { id: 'c1', messages: threeToolReply });
    expect(historyFromCache(queryClient, 'c1')).toEqual([
      { role: 'user', content: 'dig' },
      { role: 'assistant', content: 'Done digging.' },
      { role: 'user', content: 'thanks' },
      { role: 'assistant', content: 'Welcome.' },
    ]);
  });
});

describe('starting a new chat', () => {
  const newArgs = (over: Partial<Parameters<typeof sendTurn>[0]> = {}) => {
    const queryClient = new QueryClient();
    queryClient.setQueryData(queryKeys.chats, [{ id: 'old', title: 'Old', timestamp: 1, workspace_id: null }]);
    return { queryClient, chatId: 'new-1', text: 'first message', files: [], isNewChat: true, ...over };
  };

  it('puts the chat in the detail and list caches before it navigates and before the create call returns', async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((r) => (release = r));
    const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
      if (path === '/api/chats/new-1' && init?.method === 'PATCH') await gate;
      if (path === '/v1/chat/completions') return sseResponse(sseText([contentChunk('Hi')]));
      return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    const a = newArgs();
    const seenAtNavigate: Array<{ detail: unknown; listed: boolean }> = [];
    const done = sendTurn({
      ...a,
      navigate: () =>
        seenAtNavigate.push({
          detail: a.queryClient.getQueryData(queryKeys.chat('new-1')),
          listed: (a.queryClient.getQueryData<Array<{ id: string }>>(queryKeys.chats) ?? [])[0]?.id === 'new-1',
        }),
    });
    await vi.waitFor(() => expect(seenAtNavigate).toHaveLength(1));
    expect(seenAtNavigate[0]).toMatchObject({ detail: { id: 'new-1', messages: [] }, listed: true });
    release();
    expect(await done).toBe(true);
  });

  it('does not throw when the chat list is not loaded', async () => {
    mockCompletion(() => sseResponse(sseText([contentChunk('Hi')])));
    const queryClient = new QueryClient();
    const ok = await sendTurn({ queryClient, chatId: 'new-2', text: 'x', files: [], isNewChat: true });
    expect(ok).toBe(true);
    expect(queryClient.getQueryData(queryKeys.chats)).toBeUndefined();
  });

  it('removes the seeded entries when creating the chat fails', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async (path: string, init?: RequestInit) =>
        path === '/api/chats/new-1' && init?.method === 'PATCH'
          ? new Response(JSON.stringify({ error: 'nope' }), { status: 500, headers: { 'Content-Type': 'application/json' } })
          : new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } }),
      ),
    );
    const a = newArgs();
    await sendTurn(a);
    expect(a.queryClient.getQueryData(queryKeys.chat('new-1'))).toBeUndefined();
    expect((a.queryClient.getQueryData<Array<{ id: string }>>(queryKeys.chats) ?? []).map((c) => c.id)).toEqual(['old']);
  });

  it('sends a temporary chat that has no cached detail', async () => {
    const fetchMock = mockCompletion(() => sseResponse(sseText([contentChunk('Hi')])));
    const ok = await sendTurn({ queryClient: new QueryClient(), chatId: 'temp-1', text: 'hi', files: [], isNewChat: false, temporary: true });
    expect(ok).toBe(true);
    expect(fetchMock.mock.calls.some(([p]) => p === '/v1/chat/completions')).toBe(true);
  });
});

describe('a send while another chat generates', () => {
  it('posts nothing, says why, keeps the composer untouched and does not navigate', async () => {
    useStreamStore.setState({ chatId: 'other', live: null, pending: null, interrupted: null, controller: new AbortController() });
    const fetchMock = vi.fn();
    vi.stubGlobal('fetch', fetchMock);
    const navigate = vi.fn();
    const onAccepted = vi.fn();
    const a = args({ navigate, onAccepted });
    const ok = await sendTurn(a);
    expect(ok).toBe(false);
    expect(fetchMock).not.toHaveBeenCalled();
    expect(navigate).not.toHaveBeenCalled();
    expect(onAccepted).not.toHaveBeenCalled();
    expect(useToastStore.getState().toasts.some((t) => t.message === BUSY_TOAST)).toBe(true);
  });

  it('does not blame another chat when the same chat is submitted twice', async () => {
    useStreamStore.setState({ chatId: 'chat-1', live: null, pending: null, interrupted: null, controller: new AbortController() });
    vi.stubGlobal('fetch', vi.fn());
    const ok = await sendTurn(args());
    expect(ok).toBe(false);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it('Retry of the chat that is already generating is ignored without a message', async () => {
    useStreamStore.setState({ chatId: 'chat-1', live: null, pending: null, interrupted: null, controller: new AbortController() });
    await resumeTurn(new QueryClient(), 'chat-1');
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });

  it('Retry shows the same explanation', async () => {
    useStreamStore.setState({ chatId: 'other', live: null, pending: null, interrupted: null, controller: new AbortController() });
    await resumeTurn(new QueryClient(), 'chat-1');
    expect(useToastStore.getState().toasts.some((t) => t.message === BUSY_TOAST)).toBe(true);
  });
});

describe('files follow the turn', () => {
  const fileTurn = (name: string) =>
    sseResponse(
      sseText([toolCallChunk('c1', name, '{}'), toolResultChunk('c1', 'done'), contentChunk('ok')]),
    );
  const artifactInvalidations = (a: ReturnType<typeof args>) => {
    const calls: number[] = [];
    const original = a.queryClient.invalidateQueries.bind(a.queryClient);
    vi.spyOn(a.queryClient, 'invalidateQueries').mockImplementation((filters) => {
      if (JSON.stringify(filters?.queryKey) === JSON.stringify(artifactsKey({ chatId: 'chat-1' }))) {
        calls.push(1);
      }
      return original(filters);
    });
    return calls;
  };

  beforeEach(() => {
    useUiStore.setState({ artifactsOpen: false });
    useSettingsStore.setState({ modes: { ...useSettingsStore.getState().modes, fileSystemMode: false } });
  });

  it('refreshes the files list when a file tool finishes and again at the end', async () => {
    mockCompletion(() => fileTurn('create_fs_file'));
    const a = args();
    const calls = artifactInvalidations(a);
    await sendTurn(a);
    expect(calls).toHaveLength(2);
  });

  it('does not refresh the files list for a read-only tool', async () => {
    mockCompletion(() => fileTurn('read_fs_file'));
    const a = args();
    const calls = artifactInvalidations(a);
    await sendTurn(a);
    expect(calls).toHaveLength(0);
  });

  it('does not open the drawer of another chat the user moved to while the turn runs', async () => {
    window.history.pushState({}, '', '/chat/other-chat');
    mockCompletion(() => fileTurn('create_fs_file'));
    const a = args();
    a.queryClient.setQueryData(['chat', 'chat-1'], { id: 'chat-1', messages: [], file_system_mode: 1 });
    await sendTurn(a);
    expect(useUiStore.getState().artifactsOpen).toBe(false);
  });

  it('opens the files drawer once when the chat is in file-system mode, and not otherwise', async () => {
    window.history.pushState({}, '', '/chat/chat-1');
    mockCompletion(() => fileTurn('create_fs_file'));
    await sendTurn(args());
    expect(useUiStore.getState().artifactsOpen).toBe(false);

    mockCompletion(() => fileTurn('create_fs_file'));
    const a = args();
    a.queryClient.setQueryData(['chat', 'chat-1'], { id: 'chat-1', messages: [], file_system_mode: 1 });
    await sendTurn(a);
    expect(useUiStore.getState().artifactsOpen).toBe(true);
  });

  it('does not reopen a drawer the user closed during the same turn', async () => {
    window.history.pushState({}, '', '/chat/chat-1');
    mockCompletion(() =>
      sseResponse(
        sseText([
          toolCallChunk('c1', 'create_fs_file', '{}'),
          toolResultChunk('c1', 'done'),
          toolCallChunk('c2', 'create_fs_file', '{}'),
          toolResultChunk('c2', 'done'),
        ]),
      ),
    );
    const a = args();
    a.queryClient.setQueryData(['chat', 'chat-1'], { id: 'chat-1', messages: [], file_system_mode: 1 });
    let opened = 0;
    const unsubscribe = useUiStore.subscribe((s, prev) => {
      if (s.artifactsOpen && !prev.artifactsOpen) {
        opened++;
        useUiStore.setState({ artifactsOpen: false }); // the user closes it at once
      }
    });
    await sendTurn(a);
    unsubscribe();
    expect(opened).toBe(1);
  });
});

describe('the chat remembers its model', () => {
  const patchBodies = (): unknown[] => {
    const calls = (globalThis.fetch as unknown as { mock: { calls: Array<[string, RequestInit?]> } }).mock.calls;
    return calls
      .filter(([, init]) => init?.method === 'PATCH')
      .map(([, init]) => JSON.parse(String(init?.body)) as unknown);
  };

  it('puts last_model in the new-chat PATCH', async () => {
    mockCompletion(() => sseResponse(sseText([contentChunk('Hi')])));
    await sendTurn({ queryClient: new QueryClient(), chatId: 'n1', text: 'hi', files: [], isNewChat: true });
    expect(patchBodies()[0]).toMatchObject({ last_model: 'test-model' });
  });

  it('saves the model once when it differs from the stored one, and not when it is the same', async () => {
    mockCompletion(() => sseResponse(sseText([contentChunk('Hi')])));
    const a = args();
    a.queryClient.setQueryData(['chat', 'chat-1'], { id: 'chat-1', messages: [], last_model: 'old-model' });
    await sendTurn(a);
    expect(patchBodies()).toEqual([{ last_model: 'test-model' }]);

    mockCompletion(() => sseResponse(sseText([contentChunk('Hi')])));
    const b = args();
    b.queryClient.setQueryData(['chat', 'chat-1'], { id: 'chat-1', messages: [], last_model: 'test-model' });
    await sendTurn(b);
    expect(patchBodies()).toEqual([]);
  });

  it('does not PATCH the model again on the next send before the chat is refetched', async () => {
    mockCompletion(() => sseResponse(sseText([contentChunk('Hi')])));
    const a = args();
    a.queryClient.setQueryData(['chat', 'chat-1'], { id: 'chat-1', messages: [], last_model: 'old-model' });
    await sendTurn(a);
    await sendTurn(a);
    expect(patchBodies()).toEqual([{ last_model: 'test-model' }]);
  });

  it('shows no toast when the server refuses the model change', async () => {
    const fetchMock = vi.fn(async (path: string, init?: RequestInit) => {
      if (init?.method === 'PATCH') {
        return new Response(JSON.stringify({ error: 'research chat' }), { status: 400, headers: { 'Content-Type': 'application/json' } });
      }
      if (path === '/v1/chat/completions') return sseResponse(sseText([contentChunk('Hi')]));
      return new Response('{}', { status: 200, headers: { 'Content-Type': 'application/json' } });
    });
    vi.stubGlobal('fetch', fetchMock);
    const a = args();
    a.queryClient.setQueryData(['chat', 'chat-1'], { id: 'chat-1', messages: [], last_model: 'old-model' });
    await sendTurn(a);
    expect(useToastStore.getState().toasts).toHaveLength(0);
  });
});
