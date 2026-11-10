import type { QueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';
import { useSettingsStore } from '../../state/settings-store';
import { useAttachmentStore } from '../../state/attachment-store';
import { useUiStore } from '../../state/ui-store';
import { generateChatId } from '../../lib/chat-id';

/** Enters temporary mode with a fresh chat id. The server row is created lazily by the first turn. */
export function startTemporaryChat(): string {
  const id = generateChatId();
  useUiStore.getState().setTemporaryChatId(id);
  return id;
}

/** Leaves temporary mode and removes whatever the server stored for it (404 means nothing was sent). */
export async function discardTemporaryChat(queryClient: QueryClient): Promise<void> {
  const id = useUiStore.getState().temporaryChatId;
  if (!id) return;
  useUiStore.getState().setTemporaryChatId(null);
  // Files staged for it go with it.
  await useAttachmentStore.getState().discard(id);
  try {
    await chatsApi.remove(id);
  } catch {
    /* never persisted: nothing to delete */
  }
  queryClient.removeQueries({ queryKey: queryKeys.chat(id) });
  await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
}

/** Keeps the temporary chat: titles it from the first message and clears temporary mode. Returns its id. */
export async function saveTemporaryChat(
  queryClient: QueryClient,
  firstMessage: string,
): Promise<string | null> {
  const id = useUiStore.getState().temporaryChatId;
  if (!id) return null;
  const settings = useSettingsStore.getState();
  await chatsApi.patch(id, {
    title: firstMessage.substring(0, 50) || 'New Chat',
    user_preferences: settings.userPreferences,
  });
  useUiStore.getState().setTemporaryChatId(null);
  await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
  return id;
}

/**
 * Whether a temporary chat should be abandoned after a navigation. Temporary chats live on the
 * landing page: leaving it for another route discards them. Starting one from a chat page navigates
 * to the landing page first, so the move to `/` never discards it (F-10).
 */
export function shouldDiscardTemporaryChat(
  previousPath: string,
  path: string,
  hasTemporaryChat: boolean,
): boolean {
  return hasTemporaryChat && previousPath !== path && path !== '/';
}
