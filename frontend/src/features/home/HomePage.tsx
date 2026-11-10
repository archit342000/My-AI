import { MessageList } from '../chat/MessageList';
import { toTurns } from '../../lib/chat-model';
import { useChatDetail } from '../chat/useChatQueries';
import { useStreamStore } from '../../state/stream-store';
import { useUiStore } from '../../state/ui-store';
import { useSphereDim } from '../../hooks/useSphereDim';
import { OnSphere } from '../../components/background/OnSphere';

/** New-chat landing: the welcome hero and composer. In temporary mode it also shows the unsaved transcript. */
export function HomePage() {
  const temporaryChatId = useUiStore((s) => s.temporaryChatId);
  const detail = useChatDetail(temporaryChatId ?? undefined);
  const streaming = useStreamStore((s) => s.chatId === temporaryChatId && temporaryChatId !== null);
  const turns = detail.data ? toTurns(detail.data.messages) : [];
  const showTranscript = temporaryChatId !== null && (turns.length > 0 || streaming);
  // The greeting is an open screen: the sphere at full strength. A transcript is a reading screen.
  useSphereDim(showTranscript ? 'read' : 'open');

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
            <OnSphere className="greeting">
              <h1 className="greeting-text">Hello there</h1>
              <p className="greeting-sub">How can I help you today?</p>
            </OnSphere>
          </div>
        </div>
      )}
    </>
  );
}
