import { useParams } from 'react-router';
import { toTurns } from '../../lib/chat-model';
import { ApiError } from '../../api/client';
import { useChatDetail } from './useChatQueries';
import { MessageList } from './MessageList';

export function ChatPage() {
  const { chatId } = useParams();
  const { data, error, isPending } = useChatDetail(chatId);

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
      <MessageList turns={turns} chatId={data.id} />
    </>
  );
}
