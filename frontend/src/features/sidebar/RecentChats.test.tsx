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

  it('the move submenu shows each workspace with its own icon, the generic grid only for an unknown one', async () => {
    mockData();
    renderWithProviders(<SidebarChats />);
    fireEvent.contextMenu(await screen.findByText('Loose chat'));
    fireEvent.click(await screen.findByRole('menuitem', { name: /Move to workspace/ }));
    const second = await screen.findByRole('menuitem', { name: 'Second' });
    const first = await screen.findByRole('menuitem', { name: longName });
    // Each shows its own icon's drawing; an unknown icon name would fall back to the grid.
    expect(second.querySelector('svg')?.innerHTML).toContain(iconPaths('logs')?.slice(0, 20));
    expect(first.querySelector('svg')?.innerHTML).toContain(iconPaths('folder')?.slice(0, 20));
    expect(second.querySelector('svg')?.innerHTML).not.toBe(first.querySelector('svg')?.innerHTML);
  });
});
