import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/render';
import { RootLayout } from './RootLayout';
import { useUiStore } from '../state/ui-store';
import { chatsApi } from '../api/chats';
import { useUserStore } from '../state/user-store';
import * as filesApi from '../api/files';
import { useAttachmentStore } from '../state/attachment-store';
import { Link, useLocation } from 'react-router';

function LocationProbe() {
  return <div data-testid="location">{useLocation().pathname}</div>;
}

describe('RootLayout', () => {
  afterEach(() => {
    vi.restoreAllMocks();
    useUiStore.setState({ artifactsOpen: false });
  });

  it('renders the sidebar, the main area and the artifacts toggle', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    const { container } = renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(container.querySelector('#sidebar')).not.toBeNull();
    expect(container.querySelector('main')).not.toBeNull();
    expect(screen.getByRole('button', { name: 'View files and artifacts' })).toBeTruthy();
  });

  it('has one composer on the landing page and in a chat, and none on other pages', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    const home = renderWithProviders(<RootLayout />);
    expect(screen.getByPlaceholderText('Start a conversation...')).toBeTruthy();
    home.unmount();
    const chat = renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(screen.getByPlaceholderText('Start a conversation...')).toBeTruthy();
    chat.unmount();
    renderWithProviders(<RootLayout />, { route: '/logs', path: '/logs' });
    expect(screen.queryByPlaceholderText('Start a conversation...')).toBeNull();
  });

  it('the artifacts toggle flips the store flag', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.click(screen.getByRole('button', { name: 'View files and artifacts' }));
    expect(useUiStore.getState().artifactsOpen).toBe(true);
  });

  it('the artifacts toggle is hidden on Home (N5)', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    renderWithProviders(<RootLayout />);
    expect(screen.queryByRole('button', { name: 'View files and artifacts' })).toBeNull();
  });

  describe('abandoned uploads', () => {
    const staged = (key: string, fileId: string) => ({
      key,
      name: key,
      size: 1,
      mimeType: 'text/plain',
      file: new File(['x'], key),
      chatId: key,
      status: 'ready' as const,
      progress: 1,
      uploaded: { file_id: fileId, name: key, size: 1, mime_type: 'text/plain' },
      error: null,
    });
    const setup = () => {
      vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
      vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
      return vi.spyOn(filesApi, 'deleteFile').mockResolvedValue(undefined);
    };
    const links = (
      <>
        <RootLayout />
        <Link to="/chat/b">go to b</Link>
        <Link to="/">go home</Link>
        <LocationProbe />
      </>
    );

    it('leaving the landing page with files staged for an unsent new chat deletes them', async () => {
      const del = setup();
      const draft = useAttachmentStore.getState().draftChatId;
      useAttachmentStore.getState().add(draft, [staged(draft, 'f1')]);
      renderWithProviders(links, { route: '/', path: '/*' });
      fireEvent.click(screen.getByText('go to b'));
      await waitFor(() => expect(del).toHaveBeenCalledWith('f1', {}));
    });

    it('files staged in an existing chat survive a visit to another chat', async () => {
      const del = setup();
      useAttachmentStore.getState().add('a', [staged('a', 'f9')]);
      renderWithProviders(links, { route: '/chat/a', path: '/*' });
      fireEvent.click(screen.getByText('go to b'));
      fireEvent.click(await screen.findByText('go home'));
      await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/'));
      expect(del).not.toHaveBeenCalled();
      expect(useAttachmentStore.getState().lists['a']).toHaveLength(1);
    });

    it('closing the page deletes unsent files whichever route is open, even one without a composer', () => {
      const del = setup();
      useAttachmentStore.getState().add('a', [staged('a', 'f7')]);
      renderWithProviders(<RootLayout />, { route: '/logs', path: '/*' });
      const event = new Event('pagehide') as PageTransitionEvent;
      Object.defineProperty(event, 'persisted', { value: false });
      window.dispatchEvent(event);
      expect(del).toHaveBeenCalledWith('f7', { keepalive: true });
    });

    it('a new chat that was started (its files already cleared by the send) deletes nothing', async () => {
      const del = setup();
      renderWithProviders(links, { route: '/', path: '/*' });
      fireEvent.click(screen.getByText('go to b'));
      await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/chat/b'));
      expect(del).not.toHaveBeenCalled();
    });
  });

  it('shows a reload banner once the session has expired, and not before', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    renderWithProviders(<RootLayout />);
    expect(screen.queryByText('Your session has expired.')).toBeNull();
    act(() => useUserStore.getState().setSessionExpired(true));
    expect(screen.getByText('Your session has expired.')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Reload' })).toBeInTheDocument();
  });
});
