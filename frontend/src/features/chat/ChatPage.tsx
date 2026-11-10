import { useEffect, useState } from 'react';
import { useParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../../api/client';
import { chatsApi, queryKeys } from '../../api/chats';
import { showToast } from '../../components/ui/toast-store';
import { toTurns } from '../../lib/chat-model';
import { useStreamStore } from '../../state/stream-store';
import { useUiStore } from '../../state/ui-store';
import { Composer } from '../composer/Composer';
import { ArtifactDrawer } from '../artifacts/ArtifactDrawer';
import { MessageList } from './MessageList';
import { reattachTurn } from './send-turn';
import { useChatDetail } from './useChatQueries';

/** Header pill with click-to-rename (legacy `#chat-title-display`). */
function ChatTitle({ chatId, title }: { chatId: string; title: string }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(title);

  async function commit() {
    const next = draft.trim();
    setEditing(false);
    if (!next || next === title) return;
    try {
      await chatsApi.patch(chatId, { title: next });
      await queryClient.invalidateQueries({ queryKey: queryKeys.chat(chatId) });
      await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
    } catch (err) {
      showToast(err instanceof Error ? err.message : 'Rename failed', 'error');
    }
  }

  return (
    <div id="chat-title-header" className="chat-title-header">
      <div className="chat-header-content chat-title-row">
        {editing ? (
          <input
            className="chat-title-display chat-title-input"
            autoFocus
            aria-label="Chat title"
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onBlur={() => void commit()}
            onKeyDown={(e) => {
              if (e.key === 'Enter') void commit();
              if (e.key === 'Escape') setEditing(false);
            }}
          />
        ) : (
          <div
            id="chat-title-display"
            className="chat-title-display"
            role="button"
            tabIndex={0}
            title="Rename chat"
            onClick={() => {
              setDraft(title);
              setEditing(true);
            }}
            onKeyDown={(e) => {
              if (e.key === 'Enter') {
                setDraft(title);
                setEditing(true);
              }
            }}
          >
            <span className="title-text">{title}</span>
            <span className="header-rename-icon">
              <svg
                width="12"
                height="12"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z" />
              </svg>
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export function ChatPage() {
  const { chatId } = useParams();
  const { data, error, isPending, refetch } = useChatDetail(chatId);
  const queryClient = useQueryClient();
  const streaming = useStreamStore((s) => s.chatId);
  const artifactsOpen = useUiStore((s) => s.artifactsOpen);

  // Reattach to a turn the server is still generating (after reload or navigation).
  useEffect(() => {
    if (chatId && data?.is_running && !streaming) void reattachTurn(queryClient, chatId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId, data?.is_running]);

  if (isPending) return <div className="chat-loading" aria-busy="true" />;
  if (error) {
    const notFound = error instanceof ApiError && error.status === 404;
    return (
      <div className="chat-error" role="alert">
        {notFound ? 'This chat no longer exists.' : `Could not load chat: ${error.message}`}
      </div>
    );
  }

  const turns = toTurns(data.messages);
  return (
    <>
      <ChatTitle chatId={data.id} title={data.title || 'Untitled chat'} />
      <MessageList turns={turns} chatId={data.id} onChanged={() => void refetch()} />
      <Composer />
      {artifactsOpen ? <ArtifactDrawer scope={{ chatId: data.id }} /> : null}
    </>
  );
}
