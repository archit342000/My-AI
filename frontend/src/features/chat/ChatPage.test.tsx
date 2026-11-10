import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ChatPage } from './ChatPage';
import { chatsApi } from '../../api/chats';
import { ApiError } from '../../api/client';
import { useUiStore } from '../../state/ui-store';
import { plainChat, threeToolChat } from '../../test/fixtures/api';
import { useStreamStore } from '../../state/stream-store';

const detail = (over: Record<string, unknown> = {}) => ({
  id: 'c1',
  title: 'My chat',
  is_running: false,
  messages: [
    { id: 1, chat_id: 'c1', role: 'user', content: 'first question', parent_type: 'main' },
    {
      id: 2,
      chat_id: 'c1',
      role: 'assistant',
      content: 'first answer',
      parent_type: 'main',
      model: 'M',
    },
  ],
  ...over,
});

describe('ChatPage', () => {
  beforeEach(() => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue(detail() as never);
    useUiStore.setState({ artifactsOpen: false });
  });
  afterEach(() => {
    vi.restoreAllMocks();
    useStreamStore.setState({
      chatId: null,
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
  });

  it('renders the title and the persisted turns', async () => {
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(await screen.findByText('My chat')).toBeTruthy();
    expect(screen.getByText('first question')).toBeTruthy();
    expect(screen.getByText('first answer')).toBeTruthy();
  });

  it('falls back to "Untitled chat" when the title is empty', async () => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue(detail({ title: '' }) as never);
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(await screen.findByText('Untitled chat')).toBeTruthy();
  });

  it('the rename field is a pill-styled input and the header row carries no inline style', async () => {
    const { container } = renderWithProviders(<ChatPage />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    fireEvent.click(await screen.findByText('My chat'));
    const field = screen.getByLabelText('Chat title');
    expect(field).toHaveClass('chat-title-display', 'chat-title-input');
    expect(field).toHaveFocus();
    expect(container.querySelector('.chat-title-row')?.hasAttribute('style')).toBe(false);
  });

  it('shows a not-found message for a 404', async () => {
    vi.spyOn(chatsApi, 'get').mockRejectedValue(new ApiError(404, {}, 'missing'));
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(await screen.findByRole('alert')).toHaveTextContent('This chat no longer exists.');
  });

  it('tells the transcript a files drawer exists while the chat page is open', async () => {
    const { unmount } = renderWithProviders(<ChatPage />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    await screen.findByText('My chat');
    expect(useUiStore.getState().filesAvailable).toBe(true);
    unmount();
    expect(useUiStore.getState().filesAvailable).toBe(false);
  });

  it('offers a way back from a missing chat', async () => {
    vi.spyOn(chatsApi, 'get').mockRejectedValue(new ApiError(404, {}, 'missing'));
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.click(await screen.findByRole('button', { name: 'New chat' }));
    expect(await screen.findByTestId('elsewhere')).toBeTruthy();
  });

  it('keeps the chat on screen when a background refetch fails with a server error', async () => {
    const get = vi.spyOn(chatsApi, 'get').mockResolvedValue(detail() as never);
    const { client } = renderWithProviders(<ChatPage />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    expect(await screen.findByText('first answer')).toBeTruthy();
    get.mockRejectedValue(new ApiError(500, {}, 'boom'));
    void client.invalidateQueries({ queryKey: ['chat', 'c1'] }); // the hook retries a 500 for seconds
    await waitFor(() => expect(get).toHaveBeenCalledTimes(2));
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getByText('first answer')).toBeTruthy();
  });

  it('shows not-found when a refetch says the chat is gone, even with the old data cached', async () => {
    const get = vi.spyOn(chatsApi, 'get').mockResolvedValue(detail() as never);
    const { client } = renderWithProviders(<ChatPage />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    expect(await screen.findByText('first answer')).toBeTruthy();
    get.mockRejectedValue(new ApiError(404, {}, 'missing'));
    await client.invalidateQueries({ queryKey: ['chat', 'c1'] });
    expect(await screen.findByRole('alert')).toHaveTextContent('This chat no longer exists.');
    expect(screen.getByRole('button', { name: 'New chat' })).toBeTruthy();
  });

  it("keeps seeded data on screen while the chat's own turn runs and the server still says 404", async () => {
    vi.spyOn(chatsApi, 'get').mockRejectedValue(new ApiError(404, {}, 'missing'));
    useStreamStore.setState({
      chatId: 'c1',
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
    const { client } = renderWithProviders(<ChatPage />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    client.setQueryData(['chat', 'c1'], detail());
    await client.invalidateQueries({ queryKey: ['chat', 'c1'] });
    expect(screen.queryByRole('alert')).toBeNull();
    expect(await screen.findByText('My chat')).toBeTruthy();
  });

  it('shows no error for a chat that is not on the server yet while its turn runs', async () => {
    vi.spyOn(chatsApi, 'get').mockRejectedValue(new ApiError(404, {}, 'missing'));
    useStreamStore.setState({
      chatId: 'c1',
      live: null,
      pending: null,
      interrupted: null,
      controller: null,
    });
    const { container } = renderWithProviders(<ChatPage />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    await waitFor(() => expect(chatsApi.get).toHaveBeenCalled());
    expect(screen.queryByRole('alert')).toBeNull();
    expect(container.querySelector('.chat-loading')).not.toBeNull();
  });

  it('shows the error message for other failures', async () => {
    vi.spyOn(chatsApi, 'get').mockRejectedValue(new Error('boom'));
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    // The chat query retries non-404 failures a few times before it shows the error.
    expect(await screen.findByRole('alert', {}, { timeout: 10000 })).toHaveTextContent('boom');
  }, 15000);

  it('mounts the artifact panel only when artifacts are open', async () => {
    useUiStore.setState({ artifactsOpen: true });
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    await waitFor(() => expect(document.querySelector('.artifact-panel')).not.toBeNull());
  });

  it('reattaches to a turn the server is still generating', async () => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue(detail({ is_running: true }) as never);
    const fetchMock = vi.fn(async () => new Response(null, { status: 204 }));
    vi.stubGlobal('fetch', fetchMock);
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    await waitFor(() =>
      expect(fetchMock).toHaveBeenCalledWith('/api/chats/c1/stream', expect.anything()),
    );
    vi.unstubAllGlobals();
  });

  describe('with chats recorded from the real backend', () => {
    const botRows = () => document.querySelectorAll('.bot-message');

    it('draws a plain reply as one assistant row', async () => {
      vi.spyOn(chatsApi, 'get').mockResolvedValue(plainChat);
      renderWithProviders(<ChatPage />, {
        route: `/chat/${plainChat.id}`,
        path: '/chat/:chatId',
      });
      await waitFor(() => expect(botRows()).toHaveLength(1));
    });

    it('draws a reply with three tool rounds as one assistant row', async () => {
      vi.spyOn(chatsApi, 'get').mockResolvedValue(threeToolChat);
      renderWithProviders(<ChatPage />, {
        route: `/chat/${threeToolChat.id}`,
        path: '/chat/:chatId',
      });
      await waitFor(() => expect(botRows().length).toBeGreaterThan(0));
      expect(botRows()).toHaveLength(1);
    });
  });
});
