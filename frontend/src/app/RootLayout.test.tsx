import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen } from '@testing-library/react';
import { renderWithProviders } from '../test/render';
import { RootLayout } from './RootLayout';
import { useUiStore } from '../state/ui-store';
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

  it('has one composer on the landing page and in a chat, and none on other pages', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    const home = renderWithProviders(<RootLayout />);
    expect(screen.getByPlaceholderText('Type a message…')).toBeTruthy();
    home.unmount();
    const chat = renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    expect(screen.getByPlaceholderText('Type a message…')).toBeTruthy();
    chat.unmount();
    renderWithProviders(<RootLayout />, { route: '/logs', path: '/logs' });
    expect(screen.queryByPlaceholderText('Type a message…')).toBeNull();
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
