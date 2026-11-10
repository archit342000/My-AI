import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen, waitFor } from '@testing-library/react';
import { useLocation } from 'react-router';
import { renderWithProviders } from '../test/render';
import { Sidebar } from './Sidebar';
import { useUiStore } from '../state/ui-store';
import { useModalStore } from '../state/modal-store';
import { chatsApi } from '../api/chats';
import { useToastStore } from '../components/ui/toast-store';
import { ADMIN, USER, signInAs } from '../test/roles';

/** Shows the current pathname so tests can assert navigation. */
function LocationProbe() {
  const loc = useLocation();
  return <div data-testid="location">{loc.pathname}</div>;
}

const withProbe = (
  <>
    <Sidebar />
    <LocationProbe />
  </>
);

describe('Sidebar', () => {
  beforeEach(() => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    useUiStore.setState({ sidebarCollapsed: false });
    useModalStore.setState({ open: null });
  });
  afterEach(() => vi.restoreAllMocks());

  it('the collapse button flips the collapsed flag', () => {
    renderWithProviders(<Sidebar />);
    fireEvent.click(screen.getByRole('button', { name: 'Collapse sidebar' }));
    expect(useUiStore.getState().sidebarCollapsed).toBe(true);
  });

  it('settings buttons open the chat and system dialogs', () => {
    renderWithProviders(<Sidebar />);
    fireEvent.click(screen.getByRole('button', { name: 'Settings' }));
    expect(useModalStore.getState().open).toBe('chat-settings');
    fireEvent.click(screen.getByRole('button', { name: 'System settings' }));
    expect(useModalStore.getState().open).toBe('system-settings');
  });

  it('New chat navigates to the home route', () => {
    renderWithProviders(withProbe, { route: '/chat/c1', path: '/*' });
    fireEvent.click(screen.getByRole('button', { name: 'New Chat' }));
    expect(screen.getByTestId('location').textContent).toBe('/');
  });

  it('Logs is an in-app link: clicking it moves the router, not the page, and marks it current', () => {
    signInAs(ADMIN);
    renderWithProviders(withProbe, { route: '/', path: '/*' });
    const link = screen.getByRole('link', { name: 'Logs' });
    const notPrevented = fireEvent.click(link);
    expect(notPrevented).toBe(false); // the router handled it (default prevented): no document load
    expect(screen.getByTestId('location').textContent).toBe('/logs');
    expect(screen.getByRole('link', { name: 'Logs' }).getAttribute('aria-current')).toBe('page');
  });

  it('the temporary-chat button is dimmed inside a saved chat and not elsewhere', () => {
    const chat = renderWithProviders(withProbe, { route: '/chat/c1', path: '/*' });
    expect(screen.getByRole('button', { name: 'Temporary Chat' }).className).toContain('temp-chat-btn--dim');
    chat.unmount();
    renderWithProviders(withProbe, { route: '/', path: '/*' });
    expect(screen.getByRole('button', { name: 'Temporary Chat' }).className).not.toContain('temp-chat-btn--dim');
  });

  it('links to the logs page', () => {
    renderWithProviders(<Sidebar />);
    expect(screen.getByRole('link', { name: 'Logs' }).getAttribute('href')).toBe('/logs');
  });

  it('New workspace opens the name prompt and creates, then opens, the workspace (F1)', async () => {
    const create = vi.spyOn(chatsApi, 'createWorkspace').mockResolvedValue({ id: 'ws-1', name: 'Work' } as never);
    renderWithProviders(withProbe, { route: '/', path: '/*' });
    fireEvent.click(screen.getByRole('button', { name: 'New Workspace' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Work' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));
    await waitFor(() => expect(screen.getByTestId('location').textContent).toBe('/workspace/ws-1'));
    expect(create).toHaveBeenCalledWith('Work');
  });

  it('a rejected workspace create shows the server message and stays put (F1)', async () => {
    useToastStore.setState({ toasts: [] });
    vi.spyOn(chatsApi, 'createWorkspace').mockRejectedValue(new Error('name exists'));
    renderWithProviders(withProbe, { route: '/', path: '/*' });
    fireEvent.click(screen.getByRole('button', { name: 'New Workspace' }));
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Work' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));
    await waitFor(() => expect(useToastStore.getState().toasts.some((t) => t.message === 'name exists')).toBe(true));
    expect(screen.getByTestId('location').textContent).toBe('/');
  });

  it('Temporary chat starts a temporary chat on the landing page (F2)', () => {
    useUiStore.setState({ temporaryChatId: null });
    renderWithProviders(withProbe, { route: '/chat/c1', path: '/*' });
    fireEvent.click(screen.getByRole('button', { name: 'Temporary Chat' }));
    expect(screen.getByTestId('location').textContent).toBe('/');
    expect(useUiStore.getState().temporaryChatId).not.toBeNull();
  });
});

describe('Sidebar by role', () => {
  beforeEach(() => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([]);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([]);
    useUiStore.setState({ sidebarCollapsed: false });
  });
  afterEach(() => vi.restoreAllMocks());

  it('shows who is signed in, with the role on hover', () => {
    signInAs(USER);
    renderWithProviders(<Sidebar />);
    const who = screen.getByText('user@test.io');
    expect(who.getAttribute('title')).toContain('user');
  });

  it('a user has no Logs link, in the full or the collapsed sidebar', () => {
    signInAs(USER);
    const { unmount } = renderWithProviders(<Sidebar />);
    expect(screen.queryByRole('link', { name: 'Logs' })).toBeNull();
    unmount();
    useUiStore.setState({ sidebarCollapsed: true });
    renderWithProviders(<Sidebar />);
    expect(screen.queryByRole('link', { name: 'Logs' })).toBeNull();
  });

  it('the admin has the Logs link and sees their email', () => {
    signInAs(ADMIN);
    renderWithProviders(<Sidebar />);
    expect(screen.getByRole('link', { name: 'Logs' })).toBeInTheDocument();
    expect(screen.getByText('admin@test.io')).toBeInTheDocument();
  });
});
