import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '../../api/client';
import { queryKeys } from '../../api/chats';
import { Icon } from '../../components/icons/Icon';
import { iconPaths, type IconName } from '../../components/icons/icon-paths';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { showToast } from '../../components/ui/toast-store';
import { Button } from '../../components/ui/Button';
import { useUiStore } from '../../state/ui-store';
import { ArtifactPanel } from '../artifacts/ArtifactPanel';
import { useChatList, useWorkspaceList } from '../chat/useChatQueries';

/** Last-updated label for a chat card. Numbers are Unix seconds (or ms when large); strings are dates. */
function updatedLabel(ts: number | string | null | undefined): string | null {
  if (ts === null || ts === undefined || ts === '') return null;
  const date = typeof ts === 'number' ? new Date(ts < 1e12 ? ts * 1000 : ts) : new Date(ts);
  if (Number.isNaN(date.getTime())) return null;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });
}

/** Workspace page: its chats, rename/delete, and the workspace's shared artifacts. */
export function WorkspacePage() {
  const { workspaceId = '' } = useParams();
  const queryClient = useQueryClient();
  const workspaces = useWorkspaceList();
  const chats = useChatList();
  const workspace = workspaces.data?.find((w) => w.id === workspaceId);
  const members = (chats.data ?? []).filter((c) => c.workspace_id === workspaceId);
  const [name, setName] = useState<string | null>(null);
  const [confirming, setConfirming] = useState(false);
  const navigate = useNavigate();

  const rename = useMutation({
    mutationFn: (value: string) =>
      apiRequest(`/api/chats/workspaces/${encodeURIComponent(workspaceId)}`, {
        method: 'PATCH',
        json: { name: value },
      }),
    onSuccess: async () => {
      setName(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaces });
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Rename failed', 'error'),
  });

  const remove = useMutation({
    mutationFn: () =>
      apiRequest(`/api/chats/workspaces/${encodeURIComponent(workspaceId)}`, { method: 'DELETE' }),
    onSuccess: async () => {
      showToast('Workspace deleted', 'success');
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaces });
      await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
      window.location.assign('/');
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Delete failed', 'error'),
  });

  if (!workspace) {
    if (workspaces.isPending) return <div className="chat-error">Loading…</div>;
    if (workspaces.isError) return <div className="chat-error">Could not load workspaces.</div>;
    return <div className="chat-error">Workspace not found.</div>;
  }

  // The workspace's own icon, falling back to the grid when it is unset or unknown (F-47).
  const headerIcon: IconName =
    workspace.icon && iconPaths(workspace.icon as IconName) ? (workspace.icon as IconName) : 'grid';
  return (
    <div
      className="workspace-view"
      style={{
        padding: '72px 24px 24px',
        width: '100%',
        maxWidth: 960,
        margin: '0 auto',
        overflowY: 'auto',
        minHeight: 0,
      }}
    >
      <header style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <Icon name={headerIcon} size={22} />
        {name === null ? (
          <h1 className="font-heading" style={{ fontSize: '1.5rem', margin: 0, flex: 1 }}>
            {workspace.name}
          </h1>
        ) : (
          <form
            style={{ flex: 1, display: 'flex', gap: 8 }}
            onSubmit={(e) => {
              e.preventDefault();
              if (name.trim()) rename.mutate(name.trim());
            }}
          >
            <input
              aria-label="Workspace name"
              autoFocus
              value={name}
              onChange={(e) => setName(e.target.value)}
              style={{
                flex: 1,
                padding: '6px 10px',
                borderRadius: 8,
                border: '1px solid var(--glass-border)',
                background: 'var(--glass-surface)',
                color: 'var(--content-primary)',
                font: 'inherit',
              }}
            />
            <button type="submit" className="btn-primary">
              Save
            </button>
            <button type="button" className="btn-secondary" onClick={() => setName(null)}>
              Cancel
            </button>
          </form>
        )}
        {name === null ? (
          <>
            <button
              type="button"
              className="btn-ghost"
              aria-label="Rename workspace"
              onClick={() => setName(workspace.name)}
            >
              <Icon name="edit" size={16} />
            </button>
            <button
              type="button"
              className="btn-ghost"
              aria-label="Delete workspace"
              onClick={() => setConfirming(true)}
            >
              <Icon name="trash" size={16} />
            </button>
          </>
        ) : null}
        <Button
          variant="primary"
          size="sm"
          onClick={() => {
            useUiStore.getState().setNewChatWorkspaceId(workspaceId);
            navigate('/');
          }}
        >
          New chat in this workspace
        </Button>
      </header>

      <div className="workspace-chat-grid">
        {members.map((c) => {
          const updated = updatedLabel(c.timestamp);
          return (
            <Link key={c.id} to={`/chat/${c.id}`} className="workspace-chat-card glass">
              <span className="workspace-chat-card__title">{c.title || 'Untitled Chat'}</span>
              {updated ? (
                <time className="workspace-chat-card__date" dateTime={String(c.timestamp)}>
                  Updated {updated}
                </time>
              ) : null}
            </Link>
          );
        })}
        {chats.isPending ? null : members.length === 0 ? (
          <p style={{ color: 'var(--content-muted)' }}>No chats in this workspace yet.</p>
        ) : null}
      </div>

      <h2 className="font-heading" style={{ fontSize: '1.1rem', margin: '28px 0 10px' }}>
        Files
      </h2>
      <div className="artifact-inline">
        <ArtifactPanel scope={{ workspaceId }} />
      </div>

      <ConfirmDialog
        open={confirming}
        title="Delete workspace?"
        message="Delete this workspace? This cannot be undone."
        confirmLabel="Delete"
        danger
        onCancel={() => setConfirming(false)}
        onConfirm={() => {
          setConfirming(false);
          remove.mutate();
        }}
      />
    </div>
  );
}
