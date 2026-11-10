import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor, within } from '@testing-library/react';
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
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    expect(await screen.findByRole('heading', { name: 'Research' })).toBeTruthy();
    expect(screen.getByText('Paper draft')).toBeTruthy();
  });

  it('shows the empty state when the workspace has no chats', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    expect(await screen.findByText('Nothing in this workspace yet')).toBeTruthy();
    fireEvent.click(screen.getByRole('button', { name: 'Start a chat here' }));
    expect(useUiStore.getState().newChatWorkspaceId).toBe('w1');
    expect(await screen.findByTestId('elsewhere')).toBeTruthy();
    useUiStore.setState({ newChatWorkspaceId: null });
  });

  it('unknown workspace id shows not-found', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([] as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/nope',
      path: '/workspace/:workspaceId',
    });
    expect(await screen.findByRole('alert')).toHaveTextContent('This workspace no longer exists.');
    expect(screen.getByRole('link', { name: 'Go to Home' })).toBeTruthy();
  });

  it('shows the shape of the page while the workspaces load', () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockReturnValue(new Promise(() => undefined) as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    const loading = screen.getByRole('status', { name: 'Loading the workspace' });
    expect(loading.querySelectorAll('.skel').length).toBeGreaterThan(4);
  });

  it('a workspace that cannot be opened says so and can be tried again', async () => {
    const list = vi.spyOn(chatsApi, 'listWorkspaces').mockRejectedValue(new Error('down'));
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    expect(
      await screen.findByText("Couldn't open this workspace", {}, { timeout: 3000 }),
    ).toBeTruthy();
    list.mockResolvedValue(ws as never);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByRole('heading', { name: 'Research' })).toBeTruthy();
  });

  it('rename sends PATCH with the trimmed name', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    const req = vi.spyOn(client, 'apiRequest').mockResolvedValue(new Response(null) as never);
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Rename workspace' }));
    fireEvent.change(await screen.findByLabelText('Workspace name'), {
      target: { value: '  Papers  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(req).toHaveBeenCalledWith(
        '/api/chats/workspaces/w1',
        expect.objectContaining({ method: 'PATCH', json: { name: 'Papers' } }),
      ),
    );
  });

  it('a blank rename is not sent', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    const req = vi.spyOn(client, 'apiRequest');
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Rename workspace' }));
    fireEvent.change(await screen.findByLabelText('Workspace name'), { target: { value: '   ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(req).not.toHaveBeenCalled();
  });

  it('rename failure shows an error toast', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(client, 'apiRequest').mockRejectedValue(new Error('name exists'));
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Rename workspace' }));
    fireEvent.change(await screen.findByLabelText('Workspace name'), { target: { value: 'X' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() =>
      expect(useToastStore.getState().toasts.some((t) => t.message === 'name exists')).toBe(true),
    );
  });

  it('a failed workspace delete tells the user (N6)', async () => {
    useToastStore.setState({ toasts: [] });
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(client, 'apiRequest').mockRejectedValue(new Error('locked'));
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Delete workspace' }));
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Delete this workspace?' })).getByRole('button', {
        name: 'Delete workspace',
      }),
    );
    await waitFor(
      () => expect(useToastStore.getState().toasts.some((t) => t.type === 'error')).toBe(true),
      { timeout: 500 },
    );
  });

  it('shows how many chats the workspace has', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue(chats as never);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    expect(await screen.findByText('1 chat')).toBeTruthy();
  });

  it('rename uses the shared input and carries no inline style', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
    const { container } = renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Rename workspace' }));
    const field = (await screen.findByLabelText('Workspace name')) as HTMLInputElement;
    expect(field.className).toContain('ui-input');
    expect(field.value).toBe('Research');
    // It is a small pop-up attached to the button, not a centred one.
    expect(field.closest('.ui-popover')).toBeTruthy();
    expect(container.querySelector('[style]')).toBeNull();
  });

  it('deleting a workspace confirms, refreshes the lists and moves the router home without a page load', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(client, 'apiRequest').mockResolvedValue(new Response(null) as never);
    const assign = vi.fn();
    vi.stubGlobal('location', { ...window.location, assign });
    const { client: queryClient } = renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries');
    fireEvent.click(await screen.findByRole('button', { name: 'Delete workspace' }));
    fireEvent.click(
      within(screen.getByRole('dialog', { name: 'Delete this workspace?' })).getByRole('button', {
        name: 'Delete workspace',
      }),
    );
    expect(await screen.findByTestId('elsewhere')).toBeTruthy();
    expect(assign).not.toHaveBeenCalled();
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['workspaces'] });
    vi.unstubAllGlobals();
  });

  it('the icon opens the picker and a new icon is saved', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue(chats as never);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
    const setIcon = vi.spyOn(chatsApi, 'setWorkspaceIcon').mockResolvedValue({} as never);
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    fireEvent.click(await screen.findByRole('button', { name: 'Change the workspace icon' }));
    const picker = await screen.findByRole('dialog', { name: 'Workspace icon' });
    fireEvent.click(within(picker).getByRole('button', { name: 'Save' }));
    expect(setIcon).not.toHaveBeenCalled(); // nothing changed
    fireEvent.click(screen.getByRole('button', { name: 'Change the workspace icon' }));
    fireEvent.click(await screen.findByRole('button', { name: 'Rocket' }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await waitFor(() => expect(setIcon).toHaveBeenCalledWith('w1', 'rocket'));
  });

  it('chat cards say when the chat was last used and lead to it', async () => {
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
    vi.spyOn(chatsApi, 'list').mockResolvedValue([
      { ...chats[0], timestamp: Math.floor(new Date(2020, 0, 5, 9, 30).getTime() / 1000) },
    ] as never);
    vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
    renderWithProviders(<WorkspacePage />, {
      route: '/workspace/w1',
      path: '/workspace/:workspaceId',
    });
    const card = await screen.findByRole('link', { name: /Paper draft/ });
    expect(card.getAttribute('href')).toBe('/chat/c1');
    expect(card).toHaveTextContent('5 Jan 2020');
  });

  describe('files section', () => {
    const renderPage = () => {
      vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
      vi.spyOn(chatsApi, 'list').mockResolvedValue(chats as never);
      vi.spyOn(artifactsApi, 'list').mockResolvedValue([] as never);
      return renderWithProviders(<WorkspacePage />, {
        route: '/workspace/w1',
        path: '/workspace/:workspaceId',
      });
    };

    it('is always there, once, whatever the Files toggle says', async () => {
      renderPage();
      expect(await screen.findByRole('region', { name: 'Files' })).toBeTruthy();
      expect(screen.getAllByRole('heading', { name: 'Files' })).toHaveLength(1);
      expect(screen.queryByRole('button', { name: 'Close files panel' })).toBeNull();
    });

    it("a workspace whose list holds only the server's placeholder folder shows the empty state", async () => {
      vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue(ws as never);
      vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
      vi.spyOn(artifactsApi, 'list').mockResolvedValue([
        { id: '', type: 'directory', filename: 'workspace', title: 'workspace' },
      ] as never);
      renderWithProviders(<WorkspacePage />, {
        route: '/workspace/w1',
        path: '/workspace/:workspaceId',
      });
      await screen.findByRole('region', { name: 'Files' });
      await waitFor(() => expect(screen.queryByText('workspace')).toBeNull());
    });
  });
});
