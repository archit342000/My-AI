import { useRef, useState } from 'react';
import { NavLink, useMatch, useNavigate } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../api/chats';
import { discardTemporaryChat, startTemporaryChat } from '../features/chat/temporary-chat';
import { discardNewChatDraft } from '../features/composer/draft-cleanup';
import { PromptDialog } from '../components/ui/PromptDialog';
import { showToast } from '../components/ui/toast-store';
import { Icon } from '../components/icons/Icon';
import { Button, IconButton } from '../components/ui/Button';
import { Tooltip } from '../components/ui/Tooltip';
import { cx } from '../lib/cx';
import { rippleSphere } from '../lib/sphere-signal';
import { useSidebarResize } from './useSidebarResize';
import { useUiStore } from '../state/ui-store';
import { SidebarChats } from '../features/sidebar/RecentChats';
import { useOpenSettings } from '../features/settings/settings-nav';
import { useIsAdmin, useUserStore } from '../state/user-store';

/** The app's mark: two dotted rings, the dot sphere in small. Pressing it sends a ripple through the sphere. */
function AppMark() {
  return (
    <svg
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeLinecap="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="9" strokeWidth="2.2" strokeDasharray="0.1 4.6" />
      <circle cx="12" cy="12" r="4.6" strokeWidth="2" strokeDasharray="0.1 4.8" />
      <circle cx="12" cy="12" r="0.6" strokeWidth="2" />
    </svg>
  );
}

/**
 * The navigation panel (rule book 5.3): the app mark, the three start actions, workspaces and
 * chats, and Settings, System and Logs at the foot. Collapsed, it is a rail of icons with name tags.
 * On a phone it is a drawer.
 */
export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const openSettings = useOpenSettings();
  const temporaryChatId = useUiStore((s) => s.temporaryChatId);
  const isAdmin = useIsAdmin();
  const user = useUserStore((s) => s.user);
  const aside = useRef<HTMLElement>(null);
  const newWorkspaceRef = useRef<HTMLButtonElement>(null);
  const { resizing, handleProps } = useSidebarResize(aside);
  // A temporary chat starts on the home page: inside a saved chat the button is dimmed.
  const inChat = useMatch('/chat/:chatId') !== null;

  function toggleTemporary() {
    // Navigate first: the temporary chat is started on the landing page (see shouldDiscardTemporaryChat).
    if (temporaryChatId) {
      void discardTemporaryChat(queryClient);
      navigate('/');
    } else {
      navigate('/');
      startTemporaryChat();
    }
  }
  const [creating, setCreating] = useState(false);

  function newChat() {
    void discardTemporaryChat(queryClient);
    void discardNewChatDraft(queryClient);
    useUiStore.getState().setNewChatWorkspaceId(null);
    navigate('/');
  }

  async function createWorkspace(name: string) {
    setCreating(false);
    if (!name.trim()) return;
    try {
      const ws = await chatsApi.createWorkspace(name.trim());
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaces });
      navigate(`/workspace/${ws.id}`);
    } catch (err) {
      showToast(
        err instanceof Error ? err.message : 'The workspace could not be created. Try again.',
        'error',
      );
    }
  }

  return (
    <aside
      id="sidebar"
      ref={aside}
      aria-label="Chats"
      className={cx(collapsed ? 'sidebar-collapsed' : 'sidebar-expanded', resizing && 'resizing')}
    >
      <div className="resize-handle" id="sidebar-resizer" {...handleProps} />

      <div className="sidebar-header">
        <button
          type="button"
          className="sidebar-brand"
          aria-label="My AI"
          onClick={() => rippleSphere()}
        >
          <AppMark />
          <span className="sidebar-text">My AI</span>
        </button>
        <IconButton
          id="sidebar-toggle"
          icon="panel"
          label={collapsed ? 'Expand the panel' : 'Collapse the panel'}
          aria-expanded={!collapsed}
          onClick={toggle}
        />
      </div>

      <div className="sidebar-actions">
        {collapsed ? (
          <IconButton id="new-chat-btn" icon="plus" label="New chat" onClick={newChat} />
        ) : (
          <Button
            id="new-chat-btn"
            variant="quiet"
            className="sidebar-action-btn"
            onClick={newChat}
          >
            <Icon name="plus" size={16} strokeWidth={2.2} />
            <span className="sidebar-text">New chat</span>
          </Button>
        )}
        <IconButton
          id="temp-chat-btn"
          icon="temp-chat"
          label="Temporary chat"
          aria-pressed={Boolean(temporaryChatId)}
          className={cx(inChat && 'temp-chat-btn--dim')}
          onClick={toggleTemporary}
        />
        <IconButton
          id="new-folder-btn"
          ref={newWorkspaceRef}
          icon="new-workspace"
          label="New workspace"
          onClick={() => setCreating(true)}
        />
      </div>

      <div className="sidebar-content">
        <SidebarChats />
      </div>
      <PromptDialog
        open={creating}
        anchorRef={newWorkspaceRef}
        title="New workspace"
        message="Name"
        confirmLabel="Create workspace"
        onCancel={() => setCreating(false)}
        onSubmit={(v) => void createWorkspace(v)}
      />

      <div className="sidebar-footer">
        <FootItem
          id="settings-trigger"
          icon="sliders"
          label="Settings"
          collapsed={collapsed}
          onClick={() => openSettings('chat')}
        />
        <FootItem
          id="system-settings-trigger"
          icon="chip"
          label="System"
          collapsed={collapsed}
          onClick={() => openSettings('system')}
        />
        {isAdmin ? <FootItem icon="list" label="Logs" collapsed={collapsed} to="/logs" /> : null}
        {user && !collapsed ? (
          <div
            className="sidebar-user sidebar-text"
            title={`Signed in as ${user.email} (${user.role})`}
          >
            {user.email}
          </div>
        ) : null}
      </div>
    </aside>
  );
}

/** One of the entries at the foot of the panel: a link, or a button. In the rail it shows its name as a tip. */
function FootItem({
  id,
  icon,
  label,
  collapsed,
  to,
  onClick,
}: {
  id?: string;
  icon: 'sliders' | 'chip' | 'list';
  label: string;
  collapsed: boolean;
  to?: string;
  onClick?: () => void;
}) {
  const content = (
    <>
      <Icon name={icon} size={18} />
      <span className="sidebar-text">{label}</span>
    </>
  );
  const item = to ? (
    <NavLink
      to={to}
      id={id}
      aria-label={label}
      className={({ isActive }) => cx('nav-item', isActive && 'active')}
    >
      {content}
    </NavLink>
  ) : (
    <button type="button" id={id} className="nav-item" aria-label={label} onClick={onClick}>
      {content}
    </button>
  );
  return collapsed ? <Tooltip content={label}>{item}</Tooltip> : item;
}
