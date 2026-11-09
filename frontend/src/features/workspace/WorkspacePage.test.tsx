import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, screen, waitFor } from '@testing-library/react';
import { renderWithProviders } from '../../test/render';
import { WorkspacePage } from './WorkspacePage';
import { chatsApi } from '../../api/chats';
import * as client from '../../api/client';
import { useToastStore } from '../../components/ui/toast-store';
import { artifactsApi } from '../../api/filesystem';
import { useUiStore } from '../../state/ui-store';

const ws = [{ id: 'w1', name: 'Research', icon: null }];
const chats = [{ id: 'c1', title: 'Paper draft', workspace_id: 'w1' }];

describe('WorkspacePage', () => {
  beforeEach(() => {
    useUiStore.setState({ artifactsOpen: false });
  });

  afterEach(() => {
    useUiStore.setState({ artifactsOpen: false });
    vi.restoreAllMocks();
    useToastStore.setState({ toasts: [] });
  });

  it('shows the workspace name and its chats', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue(chats as never);
    renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    expect(await screen.findByRole('heading', { name: 'Research' })).toBeTruthy();
    expect(screen.getByText('Paper draft')).toBeTruthy();
  });

  it('shows the empty state when the workspace has no chats', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    expect(await screen.findByText('No chats in this workspace yet.')).toBeTruthy();
  });

  it('unknown workspace id shows not-found', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([] as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    renderWithProviders(<WorkspacePage />, { route: '/workspace/nope', path: '/workspace/:workspaceId' });
    expect(await screen.findByText('Workspace not found.')).toBeTruthy();
  });

  it('rename sends PATCH with the trimmed name', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    const req = vi.spyOn(client, 'apiRequest').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    fireEvent.click(await screen.findByRole('button', { name: 'Rename workspace' }));
    fireEvent.change(screen.getByLabelText('Workspace name'), { target: { value: '  Papers  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(req).toHaveBeenCalledWith('/api/chats/workspaces/w1', expect.objectContaining({ method: 'PATCH', json: { name: 'Papers' } })));
  });

  it('a blank rename is not sent', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    const req = vi.spyOn(client, 'apiRequest');
    renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    fireEvent.click(await screen.findByRole('button', { name: 'Rename workspace' }));
    fireEvent.change(screen.getByLabelText('Workspace name'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(req).not.toHaveBeenCalled();
  });

  it('rename failure shows an error toast', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(client, 'apiRequest').mockRejectedValue(new Error('name exists'));
    renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    fireEvent.click(await screen.findByRole('button', { name: 'Rename workspace' }));
    fireEvent.change(screen.getByLabelText('Workspace name'), { target: { value: 'X' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'name exists')).toBe(true));
  });

  it('a failed workspace delete tells the user (N6)', async () => {
    useToastStore.setState({ toasts: [] });
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(client, 'apiRequest').mockRejectedValue(new Error('locked'));
    renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    fireEvent.click(await screen.findByRole('button', { name: 'Delete workspace' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.type === 'error')).toBe(true), { timeout: 500 });
  });

  describe('files panel (the Files toggle)', () => {
    const renderPage = () => {
      vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
      vi.spyOn(chatsApi, 'list').mockResolvedValue(chats as never);
      vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
      return renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    };

    it('is hidden while the toggle is off', async () => {
      renderPage();
      expect(await screen.findByRole('heading', { name: 'Research' })).toBeTruthy();
      expect(screen.queryByRole('region', { name: 'Artifacts' })).toBeNull();
      expect(screen.queryByRole('heading', { name: 'Files' })).toBeNull();
    });

    it('is shown while the toggle is on', async () => {
      useUiStore.setState({ artifactsOpen: true });
      renderPage();
      expect(await screen.findByRole('region', { name: 'Artifacts' })).toBeTruthy();
      // the page's own heading and the panel's heading both read "Files"
      expect(screen.getAllByRole('heading', { name: 'Files' })).toHaveLength(2);
    });

    it('follows the toggle after the page has rendered', async () => {
      renderPage();
      await screen.findByRole('heading', { name: 'Research' });
      act(() => useUiStore.getState().toggleArtifacts());
      expect(await screen.findByRole('region', { name: 'Artifacts' })).toBeTruthy();
      act(() => useUiStore.getState().toggleArtifacts());
      await waitFor(() => expect(screen.queryByRole('region', { name: 'Artifacts' })).toBeNull());
    });

    it('closes from its own close button', async () => {
      useUiStore.setState({ artifactsOpen: true });
      renderPage();
      fireEvent.click(await screen.findByRole('button', { name: 'Close files panel' }));
      expect(useUiStore.getState().artifactsOpen).toBe(false);
      await waitFor(() => expect(screen.queryByRole('region', { name: 'Artifacts' })).toBeNull());
    });
  });
});
