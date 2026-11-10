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
import { stopIfStreaming } from '../chat/send-turn';
import { dayGroup, whenLabel } from '../../lib/format-time';

type Target = { kind: 'chat'; chat: ChatSummary } | { kind: 'workspace'; workspace: Workspace };
type Pending = { op: 'rename' | 'delete' | 'icon' | 'move-new'; target: Target } | null;

/** The chat list is grouped by day (rule book 5.3). */
const DAY_GROUPS = [
  { key: 'today', label: 'Today' },
  { key: 'earlier', label: 'Earlier' },
] as const;

/** Opens the menu for a row at a point; `from` is the row, which later anchors the rename pop-up. */
const MenuCtx = createContext<(t: Target, x: number, y: number, from: HTMLElement | null) => void>(
  () => undefined,
);

/** Sidebar lists: workspaces with their chats, then recent chats outside any workspace. */
export function SidebarChats() {
  const chats = useChatList();
  const workspaces = useWorkspaceList();
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const activeChat = useMatch('/chat/:chatId');
  const [menu, setMenu] = useState<{ target: Target; x: number; y: number } | null>(null);
  const [pending, setPending] = useState<Pending>(null);
  // The row whose menu was opened: the rename and new-workspace pop-ups attach to it.
  const anchorRef = useRef<HTMLElement | null>(null);

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
          icon: workspaceIconName(w),
          onSelect: () =>
            void run(
              () => chatsApi.patch(chat.id, { workspace_id: w.id }),
              'The chat could not be moved. Try again.',
            ),
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
            void run(
              () => chatsApi.patch(chat.id, { workspace_id: null }),
              'The chat could not be moved. Try again.',
            ),
        });
      }
      if (submenu.length) submenu.push({ type: 'separator', id: 'move-sep-new' });
      submenu.push({
        id: 'move-new',
        type: 'item',
        label: 'New workspace',
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
        label: 'Move all chats out',
        icon: 'close',
        onSelect: () =>
          void run(async () => {
            for (const c of (chats.data ?? []).filter((x) => x.workspace_id === workspace.id))
              await chatsApi.patch(c.id, { workspace_id: null });
          }, 'The chats could not be moved out. Try again.'),
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
    return t.kind === 'chat' ? t.chat.title || 'Untitled chat' : t.workspace.name;
  }

  async function confirmDelete(t: Target) {
    if (t.kind === 'chat') {
      // A chat that is generating is stopped first (the server's delete does not stop its turn).
      await run(async () => {
        await stopIfStreaming(t.chat.id, Boolean(t.chat.is_running));
        return chatsApi.remove(t.chat.id);
      }, 'It could not be deleted. Try again.');
      if (activeChat?.params.chatId === t.chat.id) navigate('/', { replace: true });
    } else {
      await run(
        () => chatsApi.deleteWorkspace(t.workspace.id),
        'It could not be deleted. Try again.',
      );
    }
  }

  async function submitRename(t: Target, value: string) {
    const name = value.trim();
    if (!name || name === targetName(t)) return;
    if (t.kind === 'chat')
      await run(
        () => chatsApi.patch(t.chat.id, { title: name }),
        'The name could not be changed. Try again.',
      );
    else
      await run(
        () => chatsApi.renameWorkspace(t.workspace.id, name),
        'The name could not be changed. Try again.',
      );
  }
  const temporaryChatId = useUiStore((s) => s.temporaryChatId);
  const all = (chats.data ?? []).filter((c) => c.id !== temporaryChatId);
  const loose = all.filter((c) => !c.workspace_id);

  return (
    <MenuCtx.Provider
      value={(target, x, y, from) => {
        anchorRef.current = from;
        setMenu({ target, x, y });
      }}
    >
      {workspaces.data && workspaces.data.length > 0 ? (
        <div id="folders-sidebar-section" className="sidebar-section">
          <div className="sidebar-section-label sec">
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
        <div id="chat-history-list" className="chat-history-scroll">
          {DAY_GROUPS.map(({ key, label }) => {
            const rows = loose.filter((c) => dayGroup(c.timestamp) === key);
            if (rows.length === 0) return null;
            return (
              <div key={key} className="sidebar-list" role="group" aria-label={label}>
                <div className="sidebar-section-label sec">
                  <span className="sidebar-text">{label}</span>
                </div>
                {rows.map((c) => (
                  <ChatLink key={c.id} chat={c} />
                ))}
              </div>
            );
          })}
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
        anchorRef={anchorRef}
        title={pending?.target.kind === 'workspace' ? 'Rename workspace' : 'Rename chat'}
        message="Name"
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
        anchorRef={anchorRef}
        title="Move to a new workspace"
        message="Name of the new workspace"
        confirmLabel="Create and move"
        onCancel={() => setPending(null)}
        onSubmit={(v) => {
          const t = pending?.target;
          setPending(null);
          if (t?.kind === 'chat' && v.trim()) {
            void run(async () => {
              const ws = await chatsApi.createWorkspace(v.trim());
              await chatsApi.patch(t.chat.id, { workspace_id: ws.id });
            }, 'The chat could not be moved. Try again.');
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
            void run(
              () => chatsApi.setWorkspaceIcon(t.workspace.id, icon),
              'The icon could not be changed. Try again.',
            );
        }}
      />
      <ConfirmDialog
        open={pending?.op === 'delete'}
        title={
          pending?.target.kind === 'workspace' ? 'Delete this workspace?' : 'Delete this chat?'
        }
        message={
          pending?.target.kind === 'workspace'
            ? `"${pending ? targetName(pending.target) : ''}" will be deleted. Its chats are kept and move out of the workspace.`
            : `"${pending ? targetName(pending.target) : ''}" will be deleted. This cannot be undone.`
        }
        confirmLabel={pending?.target.kind === 'workspace' ? 'Delete workspace' : 'Delete chat'}
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

/** The workspace's own icon when it names a known one, else the generic grid. */
function workspaceIconName(workspace: Workspace): IconName {
  return workspace.icon && iconPaths(workspace.icon as IconName)
    ? (workspace.icon as IconName)
    : 'grid';
}

function WorkspaceFolder({ workspace, chats }: { workspace: Workspace; chats: ChatSummary[] }) {
  const openMenu = useContext(MenuCtx);
  const queryClient = useQueryClient();
  const [dragOver, setDragOver] = useState(false);
  const navigate = useNavigate();
  const header = useRef<HTMLDivElement>(null);
  const press = useLongPress((x, y) =>
    openMenu({ kind: 'workspace', workspace }, x, y, header.current),
  );
  const [expanded, setExpanded] = useState(() => isWorkspaceExpanded(workspace.name));
  const iconName = workspaceIconName(workspace);

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
          .catch((err) =>
            showToast(
              err instanceof Error ? err.message : 'The chat could not be moved. Try again.',
              'error',
            ),
          );
      }}
    >
      <div
        ref={header}
        className={`folder-header${dragOver ? ' drag-over' : ''}`}
        {...press}
        onClick={() => navigate(`/workspace/${workspace.id}`)}
        onContextMenu={(e) => {
          e.preventDefault();
          openMenu({ kind: 'workspace', workspace }, e.clientX, e.clientY, e.currentTarget);
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
        >
          <Icon name="chevron-right" size={12} strokeWidth={2.5} className="folder-chevron" />
        </span>
        <div className="folder-title">
          {workspace.icon && !iconPaths(workspace.icon as IconName) ? (
            <span className="folder-emoji">{workspace.icon}</span>
          ) : (
            <Icon name={iconName} size={14} strokeWidth={2.5} className="folder-icon" />
          )}
          <span className="folder-name">{workspace.name}</span>
        </div>
        <span className="folder-count">{chats.length}</span>
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
  const row = useRef<HTMLDivElement>(null);
  const press = useLongPress((x, y) => openMenu({ kind: 'chat', chat }, x, y, row.current));
  const title = chat.title || 'Untitled chat';
  const when = whenLabel(chat.timestamp);
  return (
    <div className="chat-row" ref={row}>
      <NavLink
        draggable
        onDragStart={(e) => e.dataTransfer.setData('text/plain', chat.id)}
        to={`/chat/${chat.id}`}
        {...press}
        onContextMenu={(e) => {
          e.preventDefault();
          openMenu({ kind: 'chat', chat }, e.clientX, e.clientY, row.current);
        }}
        className={({ isActive }) => `chat-list-item${isActive ? ' active' : ''}`}
      >
        <div className="chat-list-item-title">
          <span className="chat-list-item-text">{title}</span>
        </div>
        {when ? <span className="chat-list-item-when dat keep">{when}</span> : null}
      </NavLink>
      <button
        type="button"
        className="chat-row__more ui-icon-button ui-icon-button--sm"
        aria-label={`More for ${title}`}
        aria-haspopup="menu"
        onClick={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          openMenu({ kind: 'chat', chat }, box.left, box.bottom + 4, row.current);
        }}
      >
        <Icon name="more" size={16} />
      </button>
    </div>
  );
}
