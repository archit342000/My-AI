import { useState } from 'react';
import { Link, useParams } from 'react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { apiRequest } from '../../api/client';
import { queryKeys } from '../../api/chats';
import { Icon } from '../../components/icons/Icon';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { showToast } from '../../components/ui/toast-store';
import { ArtifactPanel } from '../artifacts/ArtifactPanel';
import { useChatList, useWorkspaceList } from '../chat/useChatQueries';

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

  const rename = useMutation({
    mutationFn: (value: string) =>
      apiRequest(`/api/chats/workspaces/${encodeURIComponent(workspaceId)}`, { method: 'PATCH', json: { name: value } }),
    onSuccess: async () => {
      setName(null);
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaces });
    },
    onError: (e) => showToast(e instanceof Error ? e.message : 'Rename failed', 'error'),
  });

  const remove = useMutation({
    mutationFn: () => apiRequest(`/api/chats/workspaces/${encodeURIComponent(workspaceId)}`, { method: 'DELETE' }),
    onSuccess: async () => {
      showToast('Workspace deleted', 'success');
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaces });
      await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
      window.location.assign('/');
    },
  });

  if (!workspace) {
    return <div className="chat-error">{workspaces.isPending ? 'Loading…' : 'Workspace not found.'}</div>;
  }

  return (
    <div className="workspace-view" style={{ padding: '72px 24px 24px', maxWidth: 960, margin: '0 auto' }}>
      <header style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <Icon name="grid" size={22} />
        {name === null ? (
          <h1 className="font-heading" style={{ fontSize: '1.5rem', margin: 0, flex: 1 }}>{workspace.name}</h1>
        ) : (
          <form style={{ flex: 1, display: 'flex', gap: 8 }} onSubmit={(e) => { e.preventDefault(); if (name.trim()) rename.mutate(name.trim()); }}>
            <input aria-label="Workspace name" autoFocus value={name} onChange={(e) => setName(e.target.value)} style={{ flex: 1, padding: '6px 10px', borderRadius: 8, border: '1px solid var(--glass-border)', background: 'var(--glass-surface)', color: 'var(--content-primary)', font: 'inherit' }} />
            <button type="submit" className="btn-primary">Save</button>
            <button type="button" className="btn-secondary" onClick={() => setName(null)}>Cancel</button>
          </form>
        )}
        {name === null ? (
          <>
            <button type="button" className="btn-ghost" aria-label="Rename workspace" onClick={() => setName(workspace.name)}><Icon name="edit" size={16} /></button>
            <button type="button" className="btn-ghost" aria-label="Delete workspace" onClick={() => setConfirming(true)}><Icon name="trash" size={16} /></button>
          </>
        ) : null}
      </header>

      <div style={{ display: 'grid', gap: 12, gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))' }}>
        {members.map((c) => (
          <Link key={c.id} to={`/chat/${c.id}`} className="workspace-chat-row glass" style={{ display: 'block', padding: 14, borderRadius: 14, color: 'var(--content-primary)', textDecoration: 'none' }}>
            <div style={{ fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.title || 'Untitled Chat'}</div>
          </Link>
        ))}
        {chats.isPending ? null : members.length === 0 ? <p style={{ color: 'var(--content-muted)' }}>No chats in this workspace yet.</p> : null}
      </div>

      <h2 className="font-heading" style={{ fontSize: '1.1rem', margin: '28px 0 10px' }}>Files</h2>
      <div style={{ height: 420, border: '1px solid var(--glass-border)', borderRadius: 14, overflow: 'hidden' }}>
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
