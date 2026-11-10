import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { ChatPage } from './ChatPage';
import { chatsApi } from '../../api/chats';
import { ApiError } from '../../api/client';
import { useUiStore } from '../../state/ui-store';
import { plainChat, threeToolChat } from '../../test/fixtures/api';

const detail = (over: Record<string, unknown> = {}) => ({
  id: 'c1',
  title: 'My chat',
  is_running: false,
  messages: [
    { id: 1, chat_id: 'c1', role: 'user', content: 'first question', parent_type: 'main' },
    { id: 2, chat_id: 'c1', role: 'assistant', content: 'first answer', parent_type: 'main', model: 'M' },
  ],
  ...over,
});

describe('ChatPage', () => {
  beforeEach(() => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue(detail() as never);
    useUiStore.setState({ artifactsOpen: false });
  });
  afterEach(() => vi.restoreAllMocks());

  it('renders the title, the persisted turns and the composer', async () => {
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(await screen.findByText('My chat')).toBeTruthy();
    expect(screen.getByText('first question')).toBeTruthy();
    expect(screen.getByText('first answer')).toBeTruthy();
    expect(screen.getByPlaceholderText('Type a message…')).toBeTruthy();
  });

  it('falls back to "Untitled chat" when the title is empty', async () => {
    vi.spyOn(chatsApi, 'get').mockResolvedValue(detail({ title: '' }) as never);
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(await screen.findByText('Untitled chat')).toBeTruthy();
  });

  it('shows a not-found message for a 404', async () => {
    vi.spyOn(chatsApi, 'get').mockRejectedValue(new ApiError(404, {}, 'missing'));
    renderWithProviders(<ChatPage />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(await screen.findByRole('alert')).toHaveTextContent('This chat no longer exists.');
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
    await waitFor(() => expect(fetchMock).toHaveBeenCalledWith('/api/chats/c1/stream', expect.anything()));
    vi.unstubAllGlobals();
  });

  describe('with chats recorded from the real backend', () => {
    const botRows = () => document.querySelectorAll('.bot-turn');

    it('draws a plain reply as one assistant row', async () => {
      vi.spyOn(chatsApi, 'get').mockResolvedValue(plainChat);
      renderWithProviders(<ChatPage />, {
        route: `/chat/${plainChat.id}`,
        path: '/chat/:chatId',
      });
      await waitFor(() => expect(botRows()).toHaveLength(1));
    });

    // Expected to fail until the turn-model change merges: develop draws one row per stored
    // assistant message.
    it.fails('draws a reply with three tool rounds as one assistant row', async () => {
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
