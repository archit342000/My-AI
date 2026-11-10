import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { renderHook } from '@testing-library/react';
import type { ReactNode } from 'react';
import { chatsApi } from '../../api/chats';
import { modelsApi } from '../../api/settings';
import { useSettingsStore } from '../../state/settings-store';
import { useUserStore } from '../../state/user-store';
import { initUserStorage } from '../../lib/user-storage';
import { useChatSettings } from './useChatSettings';

const ADMIN = { id: 'a1', email: 'a@x', role: 'admin' } as const;
const detail = (id: string, over: Record<string, unknown> = {}) => ({
  id,
  title: id,
  messages: [],
  is_running: false,
  ...over,
});

function wrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe('useChatSettings', () => {
  beforeEach(() => {
    localStorage.clear();
    initUserStorage(ADMIN);
    useUserStore.setState({ user: ADMIN });
    useSettingsStore.getState().hydrate();
    vi.spyOn(modelsApi, 'list').mockResolvedValue([{ id: 'm1' }, { id: 'm2' }] as never);
  });
  afterEach(() => vi.restoreAllMocks());

  const render = (chatId: string | undefined) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const view = renderHook(({ id }: { id: string | undefined }) => useChatSettings(id), {
      initialProps: { id: chatId },
      wrapper: wrapper(client),
    });
    return { ...view, client };
  };

  it("applies the chat's file-system mode, persona and model when it opens", async () => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue(
      detail('c1', { file_system_mode: 1, persona_id: 'p3', last_model: 'm2' }) as never,
    );
    render('c1');
    await waitFor(() => expect(useSettingsStore.getState().modes.fileSystemMode).toBe(true));
    expect(useSettingsStore.getState().personaId).toBe('p3');
    expect(useSettingsStore.getState().model).toBe('m2');
  });

  it('does not overwrite a toggle changed meanwhile when the same chat is refetched', async () => {
    const get = vi
      .spyOn(chatsApi, 'get')
      .mockResolvedValue(detail('c1', { file_system_mode: 0, persona_id: 'applied' }) as never);
    const { client } = render('c1');
    await waitFor(() => expect(useSettingsStore.getState().personaId).toBe('applied')); // the chat's values are in
    act(() => useSettingsStore.getState().setMode('fileSystemMode', true));
    get.mockResolvedValue(detail('c1', { file_system_mode: 0 }) as never);
    await act(async () => {
      await client.invalidateQueries({ queryKey: ['chat', 'c1'] });
    });
    expect(useSettingsStore.getState().modes.fileSystemMode).toBe(true);
  });

  it("applies the next chat's values when another chat is opened", async () => {
    vi.spyOn(chatsApi, 'get').mockImplementation(
      async (id: string) =>
        detail(id, {
          file_system_mode: id === 'c1' ? 1 : 0,
          browsing_mode: id === 'c2' ? 1 : 0,
        }) as never,
    );
    const { rerender } = render('c1');
    await waitFor(() => expect(useSettingsStore.getState().modes.fileSystemMode).toBe(true));
    rerender({ id: 'c2' });
    await waitFor(() => expect(useSettingsStore.getState().modes.browsingMode).toBe(true));
    expect(useSettingsStore.getState().modes.fileSystemMode).toBe(false);
  });

  it('puts the defaults back when the chat page is left', async () => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue(detail('c1', { file_system_mode: 1 }) as never);
    const { unmount } = render('c1');
    await waitFor(() => expect(useSettingsStore.getState().modes.fileSystemMode).toBe(true));
    unmount();
    expect(useSettingsStore.getState().modes.fileSystemMode).toBe(false);
    expect(useSettingsStore.getState().chatScoped).toBe(false);
  });

  it("leaves the current model when the chat's model is not in the list", async () => {
    useSettingsStore.getState().setModel('m1', 'm1');
    vi.spyOn(chatsApi, 'get').mockResolvedValue(
      detail('c1', { last_model: 'gone', persona_id: 'applied-persona' }) as never,
    );
    render('c1');
    await waitFor(() => expect(chatsApi.get).toHaveBeenCalled());
    await waitFor(() => expect(useSettingsStore.getState().personaId).toBe('applied-persona'));
    expect(useSettingsStore.getState().model).toBe('m1');
  });

  it('still applies the model when the model list resolves after the chat', async () => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue(detail('c1', { last_model: 'm2' }) as never);
    let release: (v: unknown) => void = () => undefined;
    vi.spyOn(modelsApi, 'list').mockReturnValue(new Promise((r) => (release = r)) as never);
    render('c1');
    await new Promise((r) => setTimeout(r, 30));
    expect(useSettingsStore.getState().model).toBeNull(); // the model waits for the list
    release([{ id: 'm1' }, { id: 'm2' }]);
    await waitFor(() => expect(useSettingsStore.getState().model).toBe('m2'));
  });

  it("applies the chat's other values when the model list fails to load", async () => {
    vi.spyOn(modelsApi, 'list').mockRejectedValue(new Error('offline'));
    vi.spyOn(chatsApi, 'get').mockResolvedValue(
      detail('c1', { file_system_mode: 1, last_model: 'm2' }) as never,
    );
    useSettingsStore.getState().setModel('m1', 'm1');
    render('c1');
    await waitFor(() => expect(useSettingsStore.getState().modes.fileSystemMode).toBe(true));
    expect(useSettingsStore.getState().model).toBe('m1'); // the model needs the list; the rest does not
  });

  it('keeps setters chat-scoped from the moment the page opens, before the chat has loaded', async () => {
    vi.spyOn(chatsApi, 'get').mockReturnValue(new Promise(() => undefined) as never);
    render('c1');
    expect(useSettingsStore.getState().chatScoped).toBe(true);
    act(() => useSettingsStore.getState().setMode('browsingMode', true));
    expect(localStorage.getItem('my_ai_modes')).toBeNull();
  });

  it("applies again after StrictMode's mount, cleanup, mount", async () => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue(detail('c1', { file_system_mode: 1 }) as never);
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    const { StrictMode } = await import('react');
    renderHook(() => useChatSettings('c1'), {
      wrapper: ({ children }: { children: ReactNode }) => (
        <StrictMode>
          <QueryClientProvider client={client}>{children}</QueryClientProvider>
        </StrictMode>
      ),
    });
    await waitFor(() => expect(useSettingsStore.getState().modes.fileSystemMode).toBe(true));
  });
});
