import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/render';
import { RootLayout } from './RootLayout';
import { useUiStore } from '../state/ui-store';
import { useModalStore } from '../state/modal-store';
import { chatsApi } from '../api/chats';
import { artifactsApi } from '../api/filesystem';
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
    const { container } = renderWithProviders(<RootLayout />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    expect(container.querySelector('#sidebar')).not.toBeNull();
    expect(container.querySelector('main')).not.toBeNull();
    expect(screen.getByRole('button', { name: 'Files' })).toBeTruthy();
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
    fireEvent.click(screen.getByRole('button', { name: 'Files' }));
    expect(useUiStore.getState().artifactsOpen).toBe(true);
  });

  it('the files button is shown but disabled on Home, enabled on a chat and absent on the logs page', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    const home = renderWithProviders(<RootLayout />);
    expect(screen.getByRole('button', { name: 'Files' })).toBeDisabled();
    home.unmount();
    const chat = renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(screen.getByRole('button', { name: 'Files' })).toBeEnabled();
    chat.unmount();
    renderWithProviders(<RootLayout />, { route: '/logs', path: '/logs' });
    expect(screen.queryByRole('button', { name: 'Files' })).toBeNull();
  });

  it('has no files button on a workspace page (its page always shows the files)', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    renderWithProviders(<RootLayout />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    expect(screen.queryByRole('button', { name: 'Files' })).toBeNull();
  });

  it('the header files button asks before closing a panel with unsaved edits', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    useUiStore.setState({ artifactsOpen: true, artifactsDirty: true });
    renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.click(screen.getByRole('button', { name: 'Files' }));
    expect(useUiStore.getState().artifactsOpen).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'Discard changes' }));
    expect(useUiStore.getState().artifactsOpen).toBe(false);
    useUiStore.setState({ artifactsDirty: false });
  });

  it('marks the page is-ios on an iPhone and not on a desktop', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    vi.stubGlobal('navigator', {
      userAgent: 'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)',
      maxTouchPoints: 5,
    });
    const phone = renderWithProviders(<RootLayout />);
    expect(document.documentElement.classList.contains('is-ios')).toBe(true);
    phone.unmount();
    expect(document.documentElement.classList.contains('is-ios')).toBe(false);
    vi.unstubAllGlobals();
    renderWithProviders(<RootLayout />);
    expect(document.documentElement.classList.contains('is-ios')).toBe(false);
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

  it('dims the files button while the open chat has no files, but keeps it enabled', async () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    const button = screen.getByRole('button', { name: 'Files' });
    await waitFor(() => expect(button).toHaveClass('top-right-btn--empty'));
    expect(button).toBeEnabled();
  });

  it('does not dim the files button for a chat with files, and un-dims it when a file appears', async () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    const list = vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    const { client } = renderWithProviders(<RootLayout />, {
      route: '/chat/c1',
      path: '/chat/:chatId',
    });
    const button = screen.getByRole('button', { name: 'Files' });
    await waitFor(() => expect(button).toHaveClass('top-right-btn--empty')); // positive control
    list.mockResolvedValue([{ id: 'a', type: 'file' }] as never);
    await act(() => client.invalidateQueries({ queryKey: ['artifacts', 'c1|'] }));
    await waitFor(() => expect(button).not.toHaveClass('top-right-btn--empty'));
  });

  describe('phone drawer', () => {
    const setWidth = (width: number) => vi.stubGlobal('innerWidth', width);
    afterEach(() => {
      vi.unstubAllGlobals();
      useModalStore.setState({ open: null });
      useUiStore.setState({ sidebarCollapsed: true });
    });

    it('opening a dialog closes the open drawer on a phone, and leaves the sidebar alone on a desktop', () => {
      vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
      vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
      setWidth(390);
      useUiStore.setState({ sidebarCollapsed: false });
      renderWithProviders(<RootLayout />);
      act(() => useModalStore.getState().show('system-settings'));
      expect(useUiStore.getState().sidebarCollapsed).toBe(true);
      act(() => useModalStore.getState().close());
      setWidth(1440);
      act(() => useUiStore.setState({ sidebarCollapsed: false }));
      act(() => useModalStore.getState().show('system-settings'));
      expect(useUiStore.getState().sidebarCollapsed).toBe(false);
    });

    it('the menu button steps aside while the drawer is open', () => {
      vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
      vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
      setWidth(390);
      useUiStore.setState({ sidebarCollapsed: true });
      const { container } = renderWithProviders(<RootLayout />);
      expect(container.querySelector('.mobile-topbar')?.hasAttribute('hidden')).toBe(false);
      act(() => useUiStore.setState({ sidebarCollapsed: false }));
      expect(container.querySelector('.mobile-topbar')?.hasAttribute('hidden')).toBe(true);
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
