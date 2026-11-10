import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from '../test/render';
import { RootLayout } from './RootLayout';
import { useUiStore } from '../state/ui-store';
import { useModalStore } from '../state/modal-store';
import { chatsApi } from '../api/chats';
import { useUserStore } from '../state/user-store';

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

  it('the artifacts toggle flips the store flag', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    fireEvent.click(screen.getByRole('button', { name: 'View files and artifacts' }));
    expect(useUiStore.getState().artifactsOpen).toBe(true);
  });

  it('the files button is shown but disabled on Home, enabled on a chat and absent on the logs page', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    const home = renderWithProviders(<RootLayout />);
    expect(screen.getByRole('button', { name: 'View files and artifacts' })).toBeDisabled();
    home.unmount();
    const chat = renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(screen.getByRole('button', { name: 'View files and artifacts' })).toBeEnabled();
    chat.unmount();
    renderWithProviders(<RootLayout />, { route: '/logs', path: '/logs' });
    expect(screen.queryByRole('button', { name: 'View files and artifacts' })).toBeNull();
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
