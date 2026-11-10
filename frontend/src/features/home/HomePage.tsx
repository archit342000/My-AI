import { MessageList } from '../chat/MessageList';
import { toTurns } from '../../lib/chat-model';
import { useChatDetail } from '../chat/useChatQueries';
import { useStreamStore } from '../../state/stream-store';
import { useUiStore } from '../../state/ui-store';

/** New-chat landing: the welcome hero and composer. In temporary mode it also shows the unsaved transcript. */
export function HomePage() {
  const temporaryChatId = useUiStore((s) => s.temporaryChatId);
  const detail = useChatDetail(temporaryChatId ?? undefined);
  const streaming = useStreamStore((s) => s.chatId === temporaryChatId && temporaryChatId !== null);
  const turns = detail.data ? toTurns(detail.data.messages) : [];
  const showTranscript = temporaryChatId !== null && (turns.length > 0 || streaming);

  return (
    <>
      {showTranscript && temporaryChatId ? (
        <MessageList
          turns={turns}
          chatId={temporaryChatId}
          onChanged={() => void detail.refetch()}
        />
      ) : (
        <div id="messages">
          <div id="welcome-hero">
            <div className="empty-state-content">
              <div className="empty-state-greeting">
                <span className="greeting-text font-heading">Hello there</span>
                <span className="greeting-sub font-heading">How can I help you today?</span>
              </div>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
