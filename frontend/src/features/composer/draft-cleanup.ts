import type { QueryClient } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';
import { useAttachmentStore } from '../../state/attachment-store';

/**
 * Throws away the files staged for a new chat that was never sent (New Chat, leaving the landing page): the
 * uploaded files are deleted, and the chat row the first upload created, and the next new chat
 * gets a fresh id. Nothing happens when no file is staged.
 */
export async function discardNewChatDraft(queryClient: QueryClient): Promise<void> {
  const store = useAttachmentStore.getState();
  const key = store.draftChatId;
  if ((store.lists[key]?.length ?? 0) === 0) return;
  store.renewDraft();
  await store.discard(key);
  try {
    // The first upload created a skeleton chat row for the draft id: remove it too.
    await chatsApi.remove(key);
  } catch {
    /* the row is already gone (404): nothing to remove */
  }
  await queryClient.invalidateQueries({ queryKey: queryKeys.chats });
}
