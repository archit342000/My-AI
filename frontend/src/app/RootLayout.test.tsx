import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../test/render';
import { RootLayout } from './RootLayout';
import { useUiStore } from '../state/ui-store';
import { chatsApi } from '../api/chats';
import { artifactsApi } from '../api/filesystem';
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

  it('the artifacts toggle is hidden on Home (N5)', () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    renderWithProviders(<RootLayout />);
    expect(screen.queryByRole('button', { name: 'View files and artifacts' })).toBeNull();
  });

  it('dims the files button while the open chat has no files, but keeps it enabled', async () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    const button = screen.getByRole('button', { name: 'View files and artifacts' });
    await waitFor(() => expect(button).toHaveClass('top-right-btn--empty'));
    expect(button).toBeEnabled();
  });

  it('does not dim the files button for a chat with files, and un-dims it when a file appears', async () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    const list = vi.spyOn(artifactsApi, 'list').mockResolvedValue([]);
    const { client } = renderWithProviders(<RootLayout />, { route: '/chat/c1', path: '/chat/:chatId' });
    const button = screen.getByRole('button', { name: 'View files and artifacts' });
    await waitFor(() => expect(button).toHaveClass('top-right-btn--empty')); // positive control
    list.mockResolvedValue([{ id: 'a', type: 'file' }] as never);
    await act(() => client.invalidateQueries({ queryKey: ['artifacts', 'c1|'] }));
    await waitFor(() => expect(button).not.toHaveClass('top-right-btn--empty'));
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
