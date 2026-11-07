import { useNavigate } from 'react-router';
import { Icon } from '../components/icons/Icon';
import { useUiStore } from '../state/ui-store';
import { SidebarChats } from '../features/sidebar/RecentChats';

/**
 * Left navigation rail. Settings buttons are wired in phase 5.
 */
export function Sidebar() {
  const collapsed = useUiStore((s) => s.sidebarCollapsed);
  const toggle = useUiStore((s) => s.toggleSidebar);
  const navigate = useNavigate();

  return (
    <aside id="sidebar" className={collapsed ? 'sidebar-collapsed' : 'sidebar-expanded'}>
      <div className="resize-handle" id="sidebar-resizer" />

      <div className="sidebar-header">
        <div className="sidebar-brand">
          <svg className="sidebar-logo-icon" width="22" height="22" viewBox="0 0 32 32" fill="none" aria-hidden="true">
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
          title="Toggle sidebar"
          aria-label="Toggle sidebar"
          onClick={toggle}
        >
          <Icon name="chevron-left" size={18} strokeWidth={2.5} />
        </button>
      </div>

      <div className="sidebar-content">
        <div className="sidebar-actions">
          <button
            id="new-chat-btn"
            type="button"
            className="btn-primary sidebar-action-btn"
            title="New Chat"
            onClick={() => navigate('/')}
          >
            <Icon name="plus" size={18} strokeWidth={2.5} />
            <span className="sidebar-text">New Chat</span>
          </button>
          <button id="temp-chat-btn" type="button" className="sidebar-icon-btn" title="Temporary Chat" aria-label="Temporary Chat">
            <Icon name="clock" size={18} />
            <span className="nav-tooltip">Temporary Chat</span>
          </button>
          <button id="new-folder-btn" type="button" className="sidebar-icon-btn" title="New Workspace" aria-label="New Workspace">
            <Icon name="grid" size={18} />
            <span className="nav-tooltip">New Workspace</span>
          </button>
        </div>

        <SidebarChats />
      </div>

      <div className="sidebar-footer">
        <button id="settings-trigger" type="button" className="sidebar-footer-btn" title="Chat Settings">
          <Icon name="settings" size={18} />
          <span className="sidebar-text">Settings</span>
          <span className="nav-tooltip">Settings</span>
        </button>
        <button id="system-settings-trigger" type="button" className="sidebar-footer-btn" title="System Settings">
          <Icon name="monitor" size={18} />
          <span className="sidebar-text">System</span>
          <span className="nav-tooltip">System Settings</span>
        </button>
        <a href="/logs" className="sidebar-footer-btn" title="View Logs" style={{ textDecoration: 'none' }}>
          <Icon name="logs" size={18} />
          <span className="sidebar-text">Logs</span>
          <span className="nav-tooltip">Logs</span>
        </a>
      </div>
    </aside>
  );
}
