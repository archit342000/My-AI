import { useQueryClient } from '@tanstack/react-query';
import { useMatch, useNavigate } from 'react-router';
import { queryKeys } from '../../api/chats';
import { Notice } from '../../components/ui/Notice';
import { showToast } from '../../components/ui/toast-store';
import { useUiStore } from '../../state/ui-store';
import { saveTemporaryChat } from '../chat/temporary-chat';

/**
 * The strip across the top of the page while a temporary chat is on: it says nothing here is kept,
 * and offers the one way to keep it. The page's panel gets a dashed edge for as long as it shows.
 */
export function TemporaryNote() {
  const routeChatId = useMatch('/chat/:chatId')?.params.chatId;
  const temporaryChatId = useUiStore((s) => s.temporaryChatId);
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  if (routeChatId || temporaryChatId === null) return null;

  async function save() {
    const cached = queryClient.getQueryData<{
      messages: Array<{ role: string; content: string | null }>;
    }>(queryKeys.chat(temporaryChatId ?? ''));
    const first = cached?.messages.find((m) => m.role === 'user')?.content ?? '';
    try {
      const id = await saveTemporaryChat(queryClient, first);
      if (id) void navigate(`/chat/${id}`);
    } catch (err) {
      showToast(err instanceof Error ? err.message : "Couldn't save the chat. Try again.", 'error');
    }
  }

  return (
    <Notice className="temp-chat-banner" actionLabel="Save chat" onAction={() => void save()}>
      <span id="temp-chat-banner">
        Temporary chat. Nothing here is kept when you leave, unless you save it.
      </span>
    </Notice>
  );
}
