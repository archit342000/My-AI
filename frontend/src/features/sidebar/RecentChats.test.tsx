import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, screen } from '@testing-library/react';
import { chatsApi } from '../../api/chats';
import { renderWithProviders } from '../../test/render';
import { iconPaths } from '../../components/icons/icon-paths';
import { SidebarChats } from './RecentChats';

const longName = 'A workspace with a very long name that would push its icon out of the row'.padEnd(
  70,
  'x',
);

function mockData() {
  vi.spyOn(chatsApi, 'list').mockResolvedValue([
    { id: 'c1', title: 'First chat', workspace_id: 'w1' },
    { id: 'c2', title: 'Loose chat', workspace_id: null },
  ] as never);
  vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([
    { id: 'w1', name: longName, icon: 'folder' },
    { id: 'w2', name: 'Second', icon: 'logs' },
  ] as never);
}

afterEach(() => vi.restoreAllMocks());

describe('SidebarChats workspace rows', () => {
  it('a workspace with a long name keeps its icon and count (both in classes that never shrink) and truncates the name', async () => {
    mockData();
    const { container } = renderWithProviders(<SidebarChats />);
    const row = await screen.findByText(longName);
    expect(row.className).toBe('folder-name');
    const header = container.querySelector('.folder-header') as HTMLElement;
    expect(header.querySelector('.folder-icon')).toBeTruthy();
    expect(header.querySelector('.folder-count')?.textContent).toBe('1');
    expect(header.getAttribute('style')).toBeNull();
  });

  it('chat rows carry no inline style', async () => {
    mockData();
    const { container } = renderWithProviders(<SidebarChats />);
    await screen.findByText('Loose chat');
    expect(container.querySelector('.chat-list-item [style]')).toBeNull();
    expect(screen.getByText('Loose chat').className).toBe('chat-list-item-text');
  });

  it('the move submenu shows each workspace with its own icon', async () => {
    mockData();
    renderWithProviders(<SidebarChats />);
    fireEvent.contextMenu(await screen.findByText('Loose chat'));
    fireEvent.click(await screen.findByRole('menuitem', { name: /Move to workspace/ }));
    const second = await screen.findByRole('menuitem', { name: 'Second' });
    const first = await screen.findByRole('menuitem', { name: longName });
    // Each shows its own icon's drawing; an unknown icon name would fall back to the folder.
    expect(second.querySelector('svg')?.innerHTML).toContain(iconPaths('logs')?.slice(0, 20));
    expect(first.querySelector('svg')?.innerHTML).toContain(iconPaths('folder')?.slice(0, 20));
    expect(second.querySelector('svg')?.innerHTML).not.toBe(first.querySelector('svg')?.innerHTML);
  });
});

describe('SidebarChats day groups, times and the row menu', () => {
  const today = new Date();
  today.setHours(9, 5, 0, 0);
  const lastMonth = new Date(today.getFullYear(), today.getMonth() - 1, 3, 10, 0);

  function mockDated() {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([
      { id: 'a', title: 'Written today', workspace_id: null, timestamp: today.getTime() },
      {
        id: 'b',
        title: 'Written before',
        workspace_id: null,
        timestamp: lastMonth.getTime() / 1000,
      },
      { id: 'c', title: 'No date', workspace_id: null, timestamp: null },
    ] as never);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([] as never);
  }

  it('groups chats under Today and Earlier and shows a 24-hour time or a date', async () => {
    mockDated();
    renderWithProviders(<SidebarChats />);
    const todayGroup = await screen.findByRole('group', { name: 'Today' });
    const earlier = screen.getByRole('group', { name: 'Earlier' });
    expect(todayGroup).toHaveTextContent('Written today');
    expect(todayGroup).toHaveTextContent('09:05');
    expect(earlier).toHaveTextContent('Written before');
    expect(earlier).toHaveTextContent('No date');
    expect(earlier).toHaveTextContent(/3 [A-Z][a-z]{2}/);
  });

  it('leaves out a heading that has no chats', async () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([
      { id: 'a', title: 'Only today', workspace_id: null, timestamp: today.getTime() },
    ] as never);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([] as never);
    renderWithProviders(<SidebarChats />);
    await screen.findByRole('group', { name: 'Today' });
    expect(screen.queryByRole('group', { name: 'Earlier' })).toBeNull();
  });

  it('every chat has a named menu button that opens the same menu as a right-click', async () => {
    mockDated();
    renderWithProviders(<SidebarChats />);
    fireEvent.click(await screen.findByRole('button', { name: 'More for Written today' }));
    expect(await screen.findByRole('menuitem', { name: /Move to workspace/ })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Rename' })).toBeInTheDocument();
    expect(screen.getByRole('menuitem', { name: 'Delete' })).toBeInTheDocument();
  });

  it('Rename opens a small pop-up attached to the row, not a centred one', async () => {
    mockDated();
    renderWithProviders(<SidebarChats />);
    fireEvent.click(await screen.findByRole('button', { name: 'More for Written today' }));
    fireEvent.click(await screen.findByRole('menuitem', { name: 'Rename' }));
    const pop = await screen.findByRole('dialog', { name: 'Rename chat' });
    expect(pop.closest('.modal-backdrop')).toBeNull();
    expect(screen.getByRole('textbox', { name: 'Name' })).toHaveValue('Written today');
  });
});

describe('SidebarChats loading, problem and empty', () => {
  it('shows placeholder lines while the chats load', () => {
    vi.spyOn(chatsApi, 'list').mockReturnValue(new Promise(() => undefined) as never);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([] as never);
    renderWithProviders(<SidebarChats />);
    expect(
      screen.getByRole('status', { name: 'Loading your chats' }).querySelectorAll('.skel'),
    ).toHaveLength(5);
  });

  it('says so when the chats cannot be loaded, and Try again asks once more', async () => {
    const list = vi.spyOn(chatsApi, 'list').mockRejectedValue(new Error('down'));
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([] as never);
    renderWithProviders(<SidebarChats />);
    expect(await screen.findByRole('alert', {}, { timeout: 3000 })).toHaveTextContent(
      "Couldn't load your chats.",
    );
    list.mockResolvedValue([{ id: 'c2', title: 'Loose chat', workspace_id: null }] as never);
    fireEvent.click(screen.getByRole('button', { name: 'Try again' }));
    expect(await screen.findByText('Loose chat')).toBeTruthy();
    expect(screen.queryByRole('alert')).toBeNull();
  });

  it('says there are no chats yet when there are none', async () => {
    vi.spyOn(chatsApi, 'list').mockResolvedValue([] as never);
    vi.spyOn(chatsApi, 'listWorkspaces').mockResolvedValue([] as never);
    renderWithProviders(<SidebarChats />);
    expect(
      await screen.findByText('No chats yet. Start one and it will appear here.'),
    ).toBeTruthy();
  });
});
