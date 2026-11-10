import { useRef, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router';
import { useMutation, useQueryClient } from '@tanstack/react-query';
import { PageTitle } from '../../app/PageTitle';
import { apiRequest } from '../../api/client';
import { chatsApi, queryKeys } from '../../api/chats';
import { Icon } from '../../components/icons/Icon';
import { ConfirmDialog } from '../../components/ui/ConfirmDialog';
import { showToast } from '../../components/ui/toast-store';
import { Button, IconButton } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { PromptDialog } from '../../components/ui/PromptDialog';
import { TickRule } from '../../components/ui/TickRule';
import { fullDateTime, whenLabel } from '../../lib/format-time';
import { workspaceEmoji, workspaceIconName } from '../../lib/workspace-icon';
import { useUiStore } from '../../state/ui-store';
import { ArtifactPanel } from '../artifacts/ArtifactPanel';
import { IconPickerDialog } from '../sidebar/IconPickerDialog';
import { useChatList, useWorkspaceList } from '../chat/useChatQueries';

/**
 * Workspace page: its icon and name, its chats as cards, and the files the workspace shares
 * (always shown, one Files section).
 */
export function WorkspacePage() {
  const { workspaceId = '' } = useParams();
  const queryClient = useQueryClient();
  const workspaces = useWorkspaceList();
  const chats = useChatList();
  const workspace = workspaces.data?.find((w) => w.id === workspaceId);
  const members = (chats.data ?? []).filter((c) => c.workspace_id === workspaceId);
  const [renaming, setRenaming] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [pickingIcon, setPickingIcon] = useState(false);
  const renameButton = useRef<HTMLButtonElement>(null);
  const navigate = useNavigate();

  const rename = useMutation({
    mutationFn: (value: string) =>
      apiRequest(`/api/chats/workspaces/${encodeURIComponent(workspaceId)}`, {
        method: 'PATCH',
        json: { name: value },
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.workspaces }),
    onError: (e) =>
      showToast(e instanceof Error ? e.message : 'The workspace could not be renamed', 'error'),
  });

  const setIcon = useMutation({
    mutationFn: (icon: string | null) => chatsApi.setWorkspaceIcon(workspaceId, icon),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.workspaces }),
    onError: (e) =>
      showToast(e instanceof Error ? e.message : 'The icon could not be changed', 'error'),
  });

  const remove = useMutation({
    mutationFn: () =>
      apiRequest(`/api/chats/workspaces/${encodeURIComponent(workspaceId)}`, { method: 'DELETE' }),
    onSuccess: async () => {
      showToast('Workspace deleted', 'success');
      await queryClient.invalidateQueries({ queryKey: queryKeys.workspaces });
      await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
      navigate('/', { replace: true });
    },
    onError: (e) =>
      showToast(e instanceof Error ? e.message : 'The workspace could not be deleted', 'error'),
  });

  if (!workspace) {
    if (workspaces.isPending) return <div className="chat-loading" aria-busy="true" />;
    if (workspaces.isError)
      return (
        <div className="chat-error" role="alert">
          <span className="chat-error__message">
            Couldn't open this workspace. Your chats and files are safe.
          </span>
          <button
            type="button"
            className="chat-error__action"
            onClick={() => void workspaces.refetch()}
          >
            Try again
          </button>
        </div>
      );
    return (
      <div className="chat-error" role="alert">
        <span className="chat-error__message">This workspace no longer exists.</span>
        <button type="button" className="chat-error__action" onClick={() => navigate('/')}>
          New chat
        </button>
      </div>
    );
  }

  const headerIcon = workspaceIconName(workspace.icon);
  const startChat = () => {
    useUiStore.getState().setNewChatWorkspaceId(workspaceId);
    navigate('/');
  };
  return (
    <div className="workspace-view">
      <PageTitle>Workspace</PageTitle>
      <header className="ws-head">
        <button
          type="button"
          className="ui-icon-button ws-head__icon"
          aria-label="Change the workspace icon"
          title="Change icon"
          onClick={() => setPickingIcon(true)}
        >
          {workspaceEmoji(workspace.icon) ? (
            <span className="ws-head__emoji">{workspaceEmoji(workspace.icon)}</span>
          ) : (
            <Icon name={headerIcon} size={24} />
          )}
        </button>
        <div className="ws-head__text">
          <h1 className="ws-head__name" title={workspace.name}>
            {workspace.name}
          </h1>
          <p className="dat keep ws-head__stats">
            {members.length} {members.length === 1 ? 'chat' : 'chats'}
          </p>
        </div>
        <IconButton
          ref={renameButton}
          icon="edit"
          label="Rename workspace"
          onClick={() => setRenaming(true)}
        />
        <IconButton icon="trash" label="Delete workspace" onClick={() => setConfirming(true)} />
        <Button variant="quiet" className="ws-head__new" onClick={startChat}>
          <Icon name="plus" size={16} />
          New chat here
        </Button>
      </header>

      <section className="ws-block" aria-labelledby="ws-chats-title">
        <div className="block-head">
          <h2 id="ws-chats-title" className="sec">
            Chats
          </h2>
          <TickRule />
        </div>
        {members.length > 0 ? (
          <div className="workspace-chat-grid">
            {members.map((c) => {
              const when = whenLabel(c.timestamp);
              return (
                <Link key={c.id} to={`/chat/${c.id}`} className="workspace-chat-card">
                  {when ? (
                    <time className="dat keep" title={fullDateTime(c.timestamp)}>
                      {when}
                    </time>
                  ) : null}
                  <span className="workspace-chat-card__title">{c.title || 'Untitled chat'}</span>
                </Link>
              );
            })}
          </div>
        ) : chats.isPending ? null : (
          <EmptyState
            className="workspace-empty"
            icon={headerIcon}
            title="Nothing in this workspace yet"
            description="Chats you start here are kept together, along with the files they make."
            action={
              <Button variant="primary" onClick={startChat}>
                Start a chat here
              </Button>
            }
          />
        )}
      </section>

      <section className="ws-block" aria-labelledby="ws-files-title">
        <div className="block-head">
          <h2 id="ws-files-title" className="sec">
            Files
          </h2>
          <TickRule />
        </div>
        <div className="artifact-inline">
          <ArtifactPanel scope={{ workspaceId }} />
        </div>
      </section>

      <PromptDialog
        open={renaming}
        anchorRef={renameButton}
        title="Rename workspace"
        message="Workspace name"
        initialValue={workspace.name}
        onCancel={() => setRenaming(false)}
        onSubmit={(value) => {
          const next = value.trim();
          setRenaming(false);
          if (next && next !== workspace.name) rename.mutate(next);
        }}
      />
      <IconPickerDialog
        open={pickingIcon}
        current={workspace.icon}
        onCancel={() => setPickingIcon(false)}
        onPick={(icon) => {
          setPickingIcon(false);
          if ((icon ?? null) !== (workspace.icon ?? null)) setIcon.mutate(icon);
        }}
      />
      <ConfirmDialog
        open={confirming}
        title="Delete this workspace?"
        message={`"${workspace.name}" will be deleted. This cannot be undone.`}
        confirmLabel="Delete workspace"
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
