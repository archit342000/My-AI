import { afterEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { MemoryRouter, Route, Routes } from 'react-router';
import type { ReactNode } from 'react';
import { artifactsApi } from '../../api/filesystem';
import { useChatHasNoFiles } from './useChatHasNoFiles';

function at(route: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={client}>
        <MemoryRouter initialEntries={[route]}>
          <Routes>
            <Route path="*" element={<>{children}</>} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  };
}

describe('useChatHasNoFiles', () => {
  afterEach(() => vi.restoreAllMocks());

  it('is true once a chat page is known to have no files', async () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    const { result } = renderHook(() => useChatHasNoFiles(), { wrapper: at('/chat/c1') });
    expect(result.current).toBe(false); // not known yet
    await waitFor(() => expect(result.current).toBe(true));
  });

  it('counts folders as no files, since every chat lists its empty workspace folder', async () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([{ id: 'w', type: 'directory' }] as never);
    const { result } = renderHook(() => useChatHasNoFiles(), { wrapper: at('/chat/c1') });
    await waitFor(() => expect(result.current).toBe(true));
  });

  it('is false for a chat that has files', async () => {
    const list = vi
      .spyOn(artifactsApi, 'list')
      .mockResolvedValue([{ id: 'a', type: 'file' }] as never);
    const { result } = renderHook(() => useChatHasNoFiles(), { wrapper: at('/chat/c1') });
    await waitFor(() => expect(list).toHaveBeenCalledWith({ chatId: 'c1' }));
    expect(result.current).toBe(false);
  });

  it('a folder without an id is a folder, as in the panel', async () => {
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([
      { id: '', type: 'file', filename: 'workspace' },
    ] as never);
    const { result } = renderHook(() => useChatHasNoFiles(), { wrapper: at('/chat/c1') });
    await waitFor(() => expect(result.current).toBe(true));
  });

  it('is false, without a request, away from a chat page', () => {
    const list = vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    const { result } = renderHook(() => useChatHasNoFiles(), { wrapper: at('/') });
    expect(result.current).toBe(false);
    expect(list).not.toHaveBeenCalled();
  });
});
