import { useState } from 'react';
import { NavLink } from 'react-router';
import { Icon } from '../../components/icons/Icon';
import { iconPaths, type IconName } from '../../components/icons/icon-paths';
import { isWorkspaceExpanded, setWorkspaceExpanded } from '../../lib/workspace-prefs';
import type { ChatSummary, Workspace } from '../../api/types';
import { useChatList, useWorkspaceList } from '../chat/useChatQueries';

/** Sidebar lists: workspaces with their chats, then recent chats outside any workspace. */
export function SidebarChats() {
  const chats = useChatList();
  const workspaces = useWorkspaceList();
  const all = chats.data ?? [];
  const loose = all.filter((c) => !c.workspace_id);

  return (
    <>
      {workspaces.data && workspaces.data.length > 0 ? (
        <div id="folders-sidebar-section" className="sidebar-section">
          <div className="sidebar-section-label">
            <span className="sidebar-text">Workspaces</span>
          </div>
          <div id="folder-list" className="folder-list custom-scroll">
            {workspaces.data.map((ws) => (
              <WorkspaceFolder key={ws.id} workspace={ws} chats={all.filter((c) => c.workspace_id === ws.id)} />
            ))}
          </div>
        </div>
      ) : null}

      <div id="recent-chats-sidebar-section" className="sidebar-section">
        <div className="sidebar-section-label">
          <span className="sidebar-text">Recent Chats</span>
        </div>
        <div id="chat-history-list" className="chat-history-scroll">
          {loose.map((c) => (
            <ChatLink key={c.id} chat={c} />
          ))}
        </div>
      </div>
    </>
  );
}

function WorkspaceFolder({ workspace, chats }: { workspace: Workspace; chats: ChatSummary[] }) {
  const [expanded, setExpanded] = useState(() => isWorkspaceExpanded(workspace.name));
  const iconName = workspace.icon && iconPaths(workspace.icon as IconName) ? (workspace.icon as IconName) : null;

  function toggle() {
    const next = !expanded;
    setExpanded(next);
    setWorkspaceExpanded(workspace.name, next);
  }

  return (
    <div className={`folder-item${expanded ? ' expanded' : ''}`} data-workspace-id={workspace.id}>
      <div className="folder-header" onClick={toggle} role="button" tabIndex={0} aria-expanded={expanded}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            toggle();
          }
        }}>
        <span className="folder-chevron-wrapper" style={{ display: 'inline-flex', alignItems: 'center', justifyContent: 'center', width: 16, height: 16, flexShrink: 0 }}>
          <Icon name="chevron-right" size={12} strokeWidth={2.5} className="folder-chevron" style={{ transform: expanded ? 'rotate(90deg)' : undefined, transition: 'transform 0.2s ease' }} />
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
          {iconName ? <Icon name={iconName} size={14} strokeWidth={2.5} style={{ opacity: 0.7 }} /> : workspace.icon ? <span style={{ fontSize: 11 }}>{workspace.icon}</span> : <Icon name="grid" size={14} strokeWidth={2.5} style={{ opacity: 0.7 }} />}
          <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', fontSize: '0.8125rem', fontWeight: 600, color: 'var(--content-primary)' }}>{workspace.name}</span>
        </div>
        <span style={{ fontSize: '0.7rem', color: 'var(--content-muted)', background: 'var(--surface-secondary)', padding: '1px 6px', borderRadius: 6, fontWeight: 500 }}>{chats.length}</span>
      </div>
      {expanded ? (
        <div className="folder-content">
          {chats.map((c) => (
            <ChatLink key={c.id} chat={c} />
          ))}
        </div>
      ) : null}
    </div>
  );
}

function ChatLink({ chat }: { chat: ChatSummary }) {
  return (
    <NavLink to={`/chat/${chat.id}`} className={({ isActive }) => `chat-list-item${isActive ? ' active' : ''}`}>
      <div className="chat-list-item-title" style={{ display: 'flex', alignItems: 'center', gap: 6, overflow: 'hidden', whiteSpace: 'nowrap', flex: 1, minWidth: 0, width: '100%' }}>
        <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', display: 'block', flex: 1, minWidth: 0 }}>{chat.title || 'Untitled Chat'}</span>
      </div>
    </NavLink>
  );
}
