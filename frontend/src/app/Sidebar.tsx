import { useRef, useState } from 'react';
import { NavLink, useMatch, useNavigate } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../api/chats';
import { discardTemporaryChat, startTemporaryChat } from '../features/chat/temporary-chat';
import { discardNewChatDraft } from '../features/composer/draft-cleanup';
import { PromptDialog } from '../components/ui/PromptDialog';
import { showToast } from '../components/ui/toast-store';
import { Icon } from '../components/icons/Icon';
import { IconButton } from '../components/ui/Button';
import { Tooltip } from '../components/ui/Tooltip';
import { cx } from '../lib/cx';
import { useSidebarResize } from './useSidebarResize';
import { useUiStore } from '../state/ui-store';
import { SidebarChats } from '../features/sidebar/RecentChats';
import { useModalStore } from '../state/modal-store';
import { useIsAdmin, useUserStore } from '../state/user-store';

/**
 * Left navigation rail. Settings buttons are wired in phase 5.
 */
export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);
  const navigate = useNavigate();
  const showDialog = useModalStore((s) => s.show);
  const queryClient = useQueryClient();
  const temporaryChatId = useUiStore((s) => s.temporaryChatId);
  const isAdmin = useIsAdmin();
  const user = useUserStore((s) => s.user);
  const aside = useRef<HTMLElement>(null);
  const { resizing, handleProps } = useSidebarResize(aside);
  // Legacy dims the temporary-chat button inside a saved chat: a temporary chat starts on the landing page.
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
      showToast(err instanceof Error ? err.message : 'Failed to create workspace', 'error');
    }
  }

  return (
    <aside
      id="sidebar"
      ref={aside}
      className={cx(collapsed ? 'sidebar-collapsed' : 'sidebar-expanded', resizing && 'resizing')}
    >
      <div className="resize-handle" id="sidebar-resizer" {...handleProps} />

      <div className="sidebar-header">
        <div className="sidebar-brand">
          <svg
            className="sidebar-logo-icon"
            width="22"
            height="22"
            viewBox="0 0 32 32"
            fill="none"
            aria-hidden="true"
          >
            <defs>
              <linearGradient id="brand-grad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0" stopColor="var(--accent)" />
                <stop offset="1" stopColor="var(--accent-hover)" />
              </linearGradient>
            </defs>
            <path d="M16 2L26 12L16 30L6 12Z" fill="url(#brand-grad)" opacity="0.9" />
            <path d="M16 2L26 12H6Z" fill="white" opacity="0.3" />
            <circle cx="16" cy="12" r="2.5" fill="white" opacity="0.9" />
          </svg>
          <span className="sidebar-brand-text font-heading sidebar-text">My AI</span>
        </div>
        <button
          id="sidebar-toggle"
          type="button"
          className="sidebar-icon-btn"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          onClick={toggle}
        >
          <Icon name={collapsed ? 'chevron-right' : 'chevron-left'} size={18} strokeWidth={2.5} />
        </button>
      </div>

      <div className="sidebar-content">
        <div className="sidebar-actions">
          {collapsed ? (
            <>
              <IconButton id="new-chat-btn" icon="plus" label="New chat" onClick={newChat} />
              <IconButton
                id="temp-chat-btn"
                icon="clock"
                label="Temporary chat"
                aria-pressed={Boolean(temporaryChatId)}
                className={cx(temporaryChatId && 'ui-icon-button--active', inChat && 'temp-chat-btn--dim')}
                onClick={toggleTemporary}
              />
              <IconButton id="new-folder-btn" icon="grid-plus" label="New workspace" onClick={() => setCreating(true)} />
            </>
          ) : (
            <>
              <button
                id="new-chat-btn"
                type="button"
                className="btn-primary sidebar-action-btn"
                title="New Chat"
                onClick={newChat}
              >
                <Icon name="plus" size={18} strokeWidth={2.5} />
                <span className="sidebar-text">New Chat</span>
              </button>
              <button
                id="temp-chat-btn"
                type="button"
                className={cx('sidebar-icon-btn', temporaryChatId && 'active', inChat && 'temp-chat-btn--dim')}
                title="Temporary Chat"
                aria-label="Temporary Chat"
                aria-pressed={Boolean(temporaryChatId)}
                onClick={toggleTemporary}
              >
                <Icon name="clock" size={18} />
                <span className="nav-tooltip">Temporary Chat</span>
              </button>
              <button
                id="new-folder-btn"
                type="button"
                className="sidebar-icon-btn"
                title="New Workspace"
                aria-label="New Workspace"
                onClick={() => setCreating(true)}
              >
                <Icon name="grid-plus" size={18} />
                <span className="nav-tooltip">New Workspace</span>
              </button>
            </>
          )}
        </div>

        <SidebarChats />
      </div>
      <PromptDialog
        open={creating}
        title="Create Workspace"
        message="Enter a name for the new workspace:"
        confirmLabel="Create"
        onCancel={() => setCreating(false)}
        onSubmit={(v) => void createWorkspace(v)}
      />

      <div className="sidebar-footer">
        {collapsed ? (
          <>
            <IconButton id="settings-trigger" icon="settings" label="Settings" onClick={() => showDialog('chat-settings')} />
            <IconButton
              id="system-settings-trigger"
              icon="monitor"
              label="System settings"
              onClick={() => showDialog('system-settings')}
            />
            {isAdmin ? (
              <Tooltip content="Logs">
                <NavLink
                  to="/logs"
                  className={({ isActive }) => cx('ui-icon-button sidebar-rail__link', isActive && 'active')}
                  aria-label="Logs"
                >
                  <Icon name="logs" size={16} />
                </NavLink>
              </Tooltip>
            ) : null}
          </>
        ) : (
          <>
            <button
              id="settings-trigger"
              type="button"
              className="sidebar-footer-btn"
              title="Chat Settings"
              aria-label="Settings"
              onClick={() => showDialog('chat-settings')}
            >
              <Icon name="settings" size={18} />
              <span className="sidebar-text">Settings</span>
              <span className="nav-tooltip">Settings</span>
            </button>
            <button
              id="system-settings-trigger"
              type="button"
              className="sidebar-footer-btn"
              title="System Settings"
              aria-label="System settings"
              onClick={() => showDialog('system-settings')}
            >
              <Icon name="monitor" size={18} />
              <span className="sidebar-text">System</span>
              <span className="nav-tooltip">System Settings</span>
            </button>
            {isAdmin ? (
              <NavLink
                to="/logs"
                className={({ isActive }) => cx('sidebar-footer-btn', isActive && 'active')}
                title="View Logs"
                aria-label="Logs"
              >
                <Icon name="logs" size={18} />
                <span className="sidebar-text">Logs</span>
                <span className="nav-tooltip">Logs</span>
              </NavLink>
            ) : null}
            {user ? (
              <div className="sidebar-user sidebar-text" title={`Signed in as ${user.email} (${user.role})`}>
                {user.email}
              </div>
            ) : null}
          </>
        )}
      </div>
    </aside>
  );
}
