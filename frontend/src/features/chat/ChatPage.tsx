import { useEffect } from 'react';
import { useParams } from 'react-router';
import { useQueryClient } from '@tanstack/react-query';
import { ApiError } from '../../api/client';
import { toTurns } from '../../lib/chat-model';
import { useStreamStore } from '../../state/stream-store';
import { useUiStore } from '../../state/ui-store';
import { Composer } from '../composer/Composer';
import { ArtifactPanel } from '../artifacts/ArtifactPanel';
import { MessageList } from './MessageList';
import { reattachTurn } from './send-turn';
import { useChatDetail } from './useChatQueries';

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
      <div className="chat-title-header">
        <span className="chat-title-text font-heading">{data.title || 'Untitled chat'}</span>
      </div>
      <MessageList turns={turns} chatId={data.id} onChanged={() => void refetch()} />
      <Composer />
      {artifactsOpen ? (
        <div className="artifact-sidebar-overlay" style={{ position: 'fixed', right: 16, top: 72, bottom: 16, width: 'min(460px, 92vw)', zIndex: 50, background: 'var(--glass-surface)', backdropFilter: 'var(--glass-blur)', border: '1px solid var(--glass-border)', borderRadius: 16, overflow: 'hidden' }}>
          <ArtifactPanel scope={{ chatId: data.id }} />
        </div>
      ) : null}
    </>
  );
}
