import { useQuery } from '@tanstack/react-query';
import { useMatch } from 'react-router';
import { artifactsKey, fetchArtifactList } from '../../api/filesystem';
import { isDirectoryEntry } from './artifact-tree';

/**
 * Whether the open chat is known to have no files: `false` until the list has loaded, on pages that are not a
 * chat, and when the chat has files. Shares the panel's query key, so opening the panel costs no extra request.
 */
export function useChatHasNoFiles(): boolean {
  const chatId = useMatch('/chat/:chatId')?.params.chatId;
  const list = useQuery({
    queryKey: artifactsKey({ chatId }),
    queryFn: () => fetchArtifactList({ chatId: chatId as string }),
    enabled: Boolean(chatId),
  });
  // A chat's list always holds its empty `workspace` folder: only real files count (the panel's own rule).
  return Boolean(chatId) && list.isSuccess && list.data.files.every(isDirectoryEntry);
}
