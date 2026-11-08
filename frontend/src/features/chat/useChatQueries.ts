import { ApiError } from '../../api/client';
import { useQuery } from '@tanstack/react-query';
import { chatsApi, queryKeys } from '../../api/chats';

export function useChatList() {
  return useQuery({ queryKey: queryKeys.chats, queryFn: chatsApi.list });
}

export function useWorkspaceList() {
  return useQuery({ queryKey: queryKeys.workspaces, queryFn: chatsApi.listWorkspaces });
}

export function useChatDetail(chatId: string | undefined) {
  return useQuery({
    queryKey: queryKeys.chat(chatId ?? ''),
    queryFn: () => chatsApi.get(chatId as string),
    enabled: Boolean(chatId),
    // A temporary chat has no server row until its first turn; don't hammer on 404.
    retry: (count, err) => !(err instanceof ApiError && err.status === 404) && count < 3,
  });
}
