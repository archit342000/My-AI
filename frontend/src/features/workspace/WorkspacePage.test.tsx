import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
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

  it('shows how many chats the workspace has', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue(chats as never);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
    renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    expect(await screen.findByText('1 chat')).toBeTruthy();
  });

  it('rename uses the shared input and carries no inline style', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
    const { container } = renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    fireEvent.click(await screen.findByRole('button', { name: 'Rename workspace' }));
    expect(screen.getByLabelText('Workspace name').className).toContain('ui-input');
    expect(container.querySelector('[style]')).toBeNull();
  });

  it('deleting a workspace confirms, refreshes the lists and moves the router home without a page load', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(client, 'apiRequest').mockResolvedValue(new Response(null) as never);
    const assign = vi.fn();
    vi.stubGlobal('location', { ...window.location, assign });
    const { client: queryClient } = renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    fireEvent.click(await screen.findByRole('button', { name: 'Delete workspace' }));
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));
    expect(await screen.findByTestId('elsewhere')).toBeTruthy();
    expect(assign).not.toHaveBeenCalled();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['workspaces'] });
    vi.unstubAllGlobals();
  });

  describe('files section', () => {
    const renderPage = () => {
      vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
      vi.spyOn(chatsApi, 'list').mockResolvedValue(chats as never);
      vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
      return renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
    };

    it('is always there, once, whatever the Files toggle says', async () => {
      renderPage();
      expect(await screen.findByRole('region', { name: 'Artifacts' })).toBeTruthy();
      expect(screen.getAllByRole('heading', { name: 'Files' })).toHaveLength(1);
      expect(screen.queryByRole('button', { name: 'Close files panel' })).toBeNull();
    });

    it('a workspace whose list holds only the server\'s placeholder folder shows the empty state', async () => {
      vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
      vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
      vi.spyOn(artifactsApi, 'list').mockResolvedValue([
        { id: '', type: 'directory', filename: 'workspace', title: 'workspace' },
      ] as never);
      renderWithProviders(<WorkspacePage />, { route: '/workspace/w1', path: '/workspace/:workspaceId' });
      await screen.findByRole('region', { name: 'Artifacts' });
      await waitFor(() => expect(screen.queryByText('workspace')).toBeNull());
    });
  });
});
