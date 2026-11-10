import type { ReactNode } from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { settingsKeys } from '../../api/settings';
import { abortableSseResponse, sseResponse, sseText } from '../../test/fixtures/sse';
import { useSpeedTest } from './useSpeedTest';

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { client, ...renderHook(() => useSpeedTest(), { wrapper }) };
}

const turn = [
  { test_status: 'Starting Turn 1 (Current Context: 0/8000)' },
  { choices: [{ delta: { content: 'hi' } }] },
  {
    timings: { prompt_ms: 500, prompt_n: 1000, predicted_ms: 2000, predicted_n: 100 },
    usage: { total_tokens: 1100 },
  },
];

describe('useSpeedTest', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('runs to done with the figures of the stream and refreshes the model list', async () => {
    const fetchMock = vi.fn(async () =>
      sseResponse(sseText([...turn, { test_status: 'Completed: done' }])),
    );
    vi.stubGlobal('fetch', fetchMock);
    const { result, client } = setup();
    const invalidate = vi.spyOn(client, 'invalidateQueries');
    act(() => result.current.run('A', 8000));
    expect(result.current.phase).toBe('running');
    await waitFor(() => expect(result.current.phase).toBe('done'));
    const init = (fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1];
    expect(JSON.parse(String(init.body))).toEqual({ model: 'A', target_context_threshold: 8000 });
    expect(result.current.state.avgDecodeTps).toBe(50);
    expect(result.current.state.points).toHaveLength(1);
    expect(result.current.error).toBeNull();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: settingsKeys.models });
  });

  it('Stop aborts the request and keeps the figures gathered so far', async () => {
    let signal: AbortSignal | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        signal = init.signal as AbortSignal;
        return abortableSseResponse(turn, signal);
      }),
    );
    const { result } = setup();
    act(() => result.current.run('A', 8000));
    await waitFor(() => expect(result.current.state.turns).toBe(1));
    act(() => result.current.stop());
    await waitFor(() => expect(result.current.phase).toBe('stopped'));
    expect(signal?.aborted).toBe(true);
    expect(result.current.state.status).toBe('Stopped');
    expect(result.current.state.avgDecodeTps).toBe(50);
  });

  it('aborts when unmounted', async () => {
    let signal: AbortSignal | undefined;
    vi.stubGlobal(
      'fetch',
      vi.fn(async (_url: string, init: RequestInit) => {
        signal = init.signal as AbortSignal;
        return abortableSseResponse(turn, signal);
      }),
    );
    const { result, unmount } = setup();
    act(() => result.current.run('A', 8000));
    await waitFor(() => expect(result.current.state.turns).toBe(1));
    unmount();
    expect(signal?.aborted).toBe(true);
  });

  it('shows the message of an HTTP error', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(
        async () => new Response(JSON.stringify({ error: 'Model not found' }), { status: 404 }),
      ),
    );
    const { result } = setup();
    act(() => result.current.run('A', 8000));
    await waitFor(() => expect(result.current.phase).toBe('failed'));
    expect(result.current.error).toBe('Model not found');
  });

  it('fails a run that ends without completing and shows the last warning', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn(async () => sseResponse(sseText([{ error: 'model failed to load' }]))),
    );
    const { result } = setup();
    act(() => result.current.run('A', 8000));
    await waitFor(() => expect(result.current.phase).toBe('failed'));
    expect(result.current.error).toBe('model failed to load');
  });

  it('a second run replaces the first without the first one overwriting its state', async () => {
    const fetchMock = vi
      .fn()
      .mockImplementationOnce(async (_url: string, init: RequestInit) =>
        abortableSseResponse(turn, init.signal as AbortSignal),
      )
      .mockImplementationOnce(async () =>
        sseResponse(sseText([...turn, { test_status: 'Completed: done' }])),
      );
    vi.stubGlobal('fetch', fetchMock);
    const { result } = setup();
    act(() => result.current.run('A', 8000));
    await waitFor(() => expect(result.current.state.turns).toBe(1));
    act(() => result.current.run('B', 8000));
    await waitFor(() => expect(result.current.phase).toBe('done'));
    // The first run's abort must not flip the finished second run to "stopped".
    await new Promise((resolve) => setTimeout(resolve, 20));
    expect(result.current.phase).toBe('done');
  });
});
