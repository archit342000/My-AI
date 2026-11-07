import { useParams } from 'react-router';
import { toTurns } from '../../lib/chat-model';
import { ApiError } from '../../api/client';
import { useEffect } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useChatDetail } from './useChatQueries';
import { reattachTurn } from './send-turn';
import { useStreamStore } from '../../state/stream-store';
import { MessageList } from './MessageList';
import { Composer } from '../composer/Composer';

export function ChatPage() {
  const { chatId } = useParams();
  const { data, error, isPending, refetch } = useChatDetail(chatId);
  const queryClient = useQueryClient();
  const streaming = useStreamStore((s) => s.chatId);

  // Reattach to a turn the server is still generating (after reload or navigation).
  useEffect(() => {
    if (chatId && data?.is_running && !streaming) void reattachTurn(queryClient, chatId);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [chatId, data?.is_running]);

  if (isPending) return <main className="chat-loading" aria-busy="true" />;
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
    </>
  );
}
