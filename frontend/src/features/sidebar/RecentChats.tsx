import { createContext, useContext, useRef, useState, type TouchEvent } from 'react';
import { NavLink, useMatch, useNavigate } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';
import { Menu, type MenuEntry } from '../../components/ui/Menu';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { IconPickerDialog } from './IconPickerDialog';
import { PromptDialog } from '../../components/ui/PromptDialog';
import { useUiStore } from '../../state/ui-store';
import { showToast } from '../../components/ui/toast-store';
import { Icon } from '../../components/icons/Icon';
import { iconPaths, type IconName } from '../../components/icons/icon-paths';
import { isWorkspaceExpanded, setWorkspaceExpanded } from '../../lib/workspace-prefs';
import type { ChatSummary, Workspace } from '../../api/types';
import { useChatList, useWorkspaceList } from '../chat/useChatQueries';

type Target = { kind: 'chat'; chat: ChatSummary } | { kind: 'workspace'; workspace: Workspace };
type Pending = { op: 'rename' | 'delete' | 'icon' | 'move-new'; target: Target } | null;

const MenuCtx = createContext<(t: Target, x: number, y: number) => void>(() => undefined);

/** Sidebar lists: workspaces with their chats, then recent chats outside any workspace. */
export function SidebarChats() {
  const chats = useChatList();
  const workspaces = useWorkspaceList();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const activeChat = useMatch('/chat/:chatId');
  const [menu, setMenu] = useState<{ target: Target; x: number; y: number } | null>(null);
  const [pending, setPending] = useState<Pending>(null);

  async function run(action: () => Promise<unknown>, failure: string) {
    try {
      await action();
      await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaces });
    } catch (err) {
      showToast(err instanceof Error ? err.message : failure, 'error');
    }
  }

  function menuItems(target: Target): MenuEntry[] {
    if (target.kind === 'chat') {
      const { chat } = target;
      const destinations: MenuEntry[] = (workspaces.data ?? [])
        .filter((w) => w.id !== chat.workspace_id)
        .map((w) => ({
          id: `move-${w.id}`,
          type: 'item' as const,
          label: w.name,
          icon: 'grid' as const,
          onSelect: () =>
            void run(() => chatsApi.patch(chat.id, { workspace_id: w.id }), 'Move failed'),
        }));
      const submenu: MenuEntry[] = [...destinations];
      if (chat.workspace_id) {
        if (submenu.length) submenu.push({ type: 'separator', id: 'move-sep' });
        submenu.push({
          id: 'move-none',
          type: 'item',
          label: 'Remove from workspace',
          icon: 'close',
          onSelect: () =>
            void run(() => chatsApi.patch(chat.id, { workspace_id: null }), 'Move failed'),
        });
      }
      if (submenu.length) submenu.push({ type: 'separator', id: 'move-sep-new' });
      submenu.push({
        id: 'move-new',
        type: 'item',
        label: 'New workspace…',
        icon: 'plus',
        onSelect: () => setPending({ op: 'move-new', target }),
      });
      return [
        {
          type: 'submenu',
          id: 'move',
          label: 'Move to workspace',
          icon: 'grid',
          searchable: (workspaces.data ?? []).length > 8,
          items: submenu,
        },
        { type: 'separator', id: 'sep-actions' },
        {
          id: 'rename',
          label: 'Rename',
          icon: 'edit',
          onSelect: () => setPending({ op: 'rename', target }),
        },
        { type: 'separator', id: 'sep-danger' },
        {
          id: 'delete',
          label: 'Delete',
          icon: 'trash',
          danger: true,
          onSelect: () => setPending({ op: 'delete', target }),
        },
      ];
    }
    const { workspace } = target;
    return [
      {
        id: 'rename',
        label: 'Rename',
        icon: 'edit',
        onSelect: () => setPending({ op: 'rename', target }),
      },
      {
        id: 'icon',
        label: 'Change icon',
        icon: 'grid',
        onSelect: () => setPending({ op: 'icon', target }),
      },
      { type: 'separator', id: 'sep-actions' },
      {
        id: 'uncategorize',
        label: 'Uncategorize all chats',
        icon: 'close',
        onSelect: () =>
          void run(async () => {
            for (const c of (chats.data ?? []).filter((x) => x.workspace_id === workspace.id))
              await chatsApi.patch(c.id, { workspace_id: null });
          }, 'Failed to uncategorize'),
      },
      { type: 'separator', id: 'sep-danger' },
      {
        id: 'delete',
        label: 'Delete',
        icon: 'trash',
        danger: true,
        onSelect: () => setPending({ op: 'delete', target }),
      },
    ];
  }

  function targetName(t: Target): string {
    return t.kind === 'chat' ? t.chat.title || 'Untitled Chat' : t.workspace.name;
  }

  async function confirmDelete(t: Target) {
    if (t.kind === 'chat') {
      await run(() => chatsApi.remove(t.chat.id), 'Delete failed');
      if (activeChat?.params.chatId === t.chat.id) navigate('/', { replace: true });
    } else {
      await run(() => chatsApi.deleteWorkspace(t.workspace.id), 'Delete failed');
    }
  }

  async function submitRename(t: Target, value: string) {
    const name = value.trim();
    if (!name || name === targetName(t)) return;
    if (t.kind === 'chat')
      await run(() => chatsApi.patch(t.chat.id, { title: name }), 'Rename failed');
    else await run(() => chatsApi.renameWorkspace(t.workspace.id, name), 'Rename failed');
  }
  const temporaryChatId = useUiStore((s) => s.temporaryChatId);
  const all = (chats.data ?? []).filter((c) => c.id !== temporaryChatId);
  const loose = all.filter((c) => !c.workspace_id);

  return (
    <MenuCtx.Provider value={(target, x, y) => setMenu({ target, x, y })}>
      {workspaces.data && workspaces.data.length > 0 ? (
        <div id="folders-sidebar-section" className="sidebar-section">
          <div className="sidebar-section-label">
            <span className="sidebar-text">Workspaces</span>
          </div>
          <div id="folder-list" className="folder-list custom-scroll">
            {workspaces.data.map((ws) => (
              <WorkspaceFolder
                key={ws.id}
                workspace={ws}
                chats={all.filter((c) => c.workspace_id === ws.id)}
              />
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
      <Menu
        label={menu ? targetName(menu.target) : 'Chat actions'}
        point={menu ? { x: menu.x, y: menu.y } : null}
        items={menu ? menuItems(menu.target) : []}
        onClose={() => setMenu(null)}
      />
      <PromptDialog
        open={pending?.op === 'rename'}
        title={pending?.target.kind === 'workspace' ? 'Rename Workspace' : 'Rename Chat'}
        message={
          pending?.target.kind === 'workspace'
            ? 'Enter new name for workspace:'
            : 'Enter a new title:'
        }
        initialValue={pending ? targetName(pending.target) : ''}
        confirmLabel="Rename"
        onCancel={() => setPending(null)}
        onSubmit={(v) => {
          const t = pending?.target;
          setPending(null);
          if (t) void submitRename(t, v);
        }}
      />
      <PromptDialog
        open={pending?.op === 'move-new'}
        title="Move to Workspace"
        message="Name of the new workspace:"
        confirmLabel="Move"
        onCancel={() => setPending(null)}
        onSubmit={(v) => {
          const t = pending?.target;
          setPending(null);
          if (t?.kind === 'chat' && v.trim()) {
            void run(async () => {
              const ws = await chatsApi.createWorkspace(v.trim());
              await chatsApi.patch(t.chat.id, { workspace_id: ws.id });
            }, 'Move failed');
          }
        }}
      />
      <IconPickerDialog
        open={pending?.op === 'icon'}
        current={pending?.target.kind === 'workspace' ? pending.target.workspace.icon : null}
        onCancel={() => setPending(null)}
        onPick={(icon) => {
          const t = pending?.target;
          setPending(null);
          if (t?.kind === 'workspace')
            void run(() => chatsApi.setWorkspaceIcon(t.workspace.id, icon), 'Icon update failed');
        }}
      />
      <ConfirmDialog
        open={pending?.op === 'delete'}
        title={pending?.target.kind === 'workspace' ? 'Delete Workspace' : 'Delete Chat'}
        message={
          pending?.target.kind === 'workspace'
            ? `Delete the workspace "${pending ? targetName(pending.target) : ''}"? The chats inside will be moved to uncategorized.`
            : `Delete "${pending ? targetName(pending.target) : ''}"? This cannot be undone.`
        }
        confirmLabel="Delete"
        danger
        onCancel={() => setPending(null)}
        onConfirm={() => {
          const t = pending?.target;
          setPending(null);
          if (t) void confirmDelete(t);
        }}
      />
    </MenuCtx.Provider>
  );
}

/** 500 ms touch long-press opens the context menu (legacy touchstart/touchend logic). */
function useLongPress(open: (x: number, y: number) => void) {
  const timer = useRef<number | undefined>(undefined);
  const fired = useRef(false);
  const start = useRef({ x: 0, y: 0 });
  return {
    onTouchStart: (e: TouchEvent<HTMLElement>) => {
      const t = e.touches[0]!;
      fired.current = false;
      start.current = { x: t.clientX, y: t.clientY };
      timer.current = window.setTimeout(() => {
        fired.current = true;
        navigator.vibrate?.(50);
        open(start.current.x, start.current.y);
      }, 500);
    },
    onTouchMove: (e: TouchEvent<HTMLElement>) => {
      const t = e.touches[0]!;
      if (Math.abs(t.clientX - start.current.x) > 10 || Math.abs(t.clientY - start.current.y) > 10)
        window.clearTimeout(timer.current);
    },
    onTouchEnd: (e: TouchEvent<HTMLElement>) => {
      window.clearTimeout(timer.current);
      if (fired.current && e.cancelable) e.preventDefault();
    },
  };
}

function WorkspaceFolder({ workspace, chats }: { workspace: Workspace; chats: ChatSummary[] }) {
  const openMenu = useContext(MenuCtx);
  const queryClient = useQueryClient();
  const [dragOver, setDragOver] = useState(false);
  const navigate = useNavigate();
  const press = useLongPress((x, y) => openMenu({ kind: 'workspace', workspace }, x, y));
  const [expanded, setExpanded] = useState(() => isWorkspaceExpanded(workspace.name));
  const iconName =
    workspace.icon && iconPaths(workspace.icon as IconName) ? (workspace.icon as IconName) : null;

  function toggle() {
    const next = !expanded;
    setExpanded(next);
    setWorkspaceExpanded(workspace.name, next);
  }

  return (
    <div
      className={`folder-item${expanded ? ' expanded' : ''}`}
      data-workspace-id={workspace.id}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        const chatId = e.dataTransfer.getData('text/plain');
        if (!chatId) return;
        void chatsApi
          .patch(chatId, { workspace_id: workspace.id })
          .then(() =>
            Promise.all([
              queryClient.invalidateQueries({ queryKey: queryKeys.chats }),
              queryClient.invalidateQueries({ queryKey: queryKeys.workspaces }),
            ]),
          )
          .catch((err) => showToast(err instanceof Error ? err.message : 'Move failed', 'error'));
      }}
    >
      <div
        className={`folder-header${dragOver ? ' drag-over' : ''}`}
        {...press}
        onClick={() => navigate(`/workspace/${workspace.id}`)}
        onContextMenu={(e) => {
          e.preventDefault();
          openMenu({ kind: 'workspace', workspace }, e.clientX, e.clientY);
        }}
        role="button"
        tabIndex={0}
        aria-expanded={expanded}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            navigate(`/workspace/${workspace.id}`);
          }
        }}
      >
        <span
          className="folder-chevron-wrapper"
          onClick={(e) => {
            e.stopPropagation();
            toggle();
          }}
          style={{
            cursor: 'pointer',
            display: 'inline-flex',
            alignItems: 'center',
            justifyContent: 'center',
            width: 16,
            height: 16,
            flexShrink: 0,
          }}
        >
          <Icon
            name="chevron-right"
            size={12}
            strokeWidth={2.5}
            className="folder-chevron"
            style={{
              transform: expanded ? 'rotate(90deg)' : undefined,
              transition: 'transform 0.2s ease',
            }}
          />
        </span>
        <div style={{ display: 'flex', alignItems: 'center', gap: 8, flex: 1, minWidth: 0 }}>
          {iconName ? (
            <Icon name={iconName} size={14} strokeWidth={2.5} style={{ opacity: 0.7 }} />
          ) : workspace.icon ? (
            <span style={{ fontSize: 11 }}>{workspace.icon}</span>
          ) : (
            <Icon name="grid" size={14} strokeWidth={2.5} style={{ opacity: 0.7 }} />
          )}
          <span
            style={{
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
              fontSize: '0.8125rem',
              fontWeight: 600,
              color: 'var(--content-primary)',
            }}
          >
            {workspace.name}
          </span>
        </div>
        <span
          style={{
            fontSize: '0.7rem',
            color: 'var(--content-muted)',
            background: 'var(--surface-secondary)',
            padding: '1px 6px',
            borderRadius: 6,
            fontWeight: 500,
          }}
        >
          {chats.length}
        </span>
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
  const openMenu = useContext(MenuCtx);
  const press = useLongPress((x, y) => openMenu({ kind: 'chat', chat }, x, y));
  return (
    <NavLink
      draggable
      onDragStart={(e) => e.dataTransfer.setData('text/plain', chat.id)}
      to={`/chat/${chat.id}`}
      {...press}
      onContextMenu={(e) => {
        e.preventDefault();
        openMenu({ kind: 'chat', chat }, e.clientX, e.clientY);
      }}
      className={({ isActive }) => `chat-list-item${isActive ? ' active' : ''}`}
    >
      <div
        className="chat-list-item-title"
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: 6,
          overflow: 'hidden',
          whiteSpace: 'nowrap',
          flex: 1,
          minWidth: 0,
          width: '100%',
        }}
      >
        <span
          style={{
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            whiteSpace: 'nowrap',
            display: 'block',
            flex: 1,
            minWidth: 0,
          }}
        >
          {chat.title || 'Untitled Chat'}
        </span>
      </div>
    </NavLink>
  );
}
