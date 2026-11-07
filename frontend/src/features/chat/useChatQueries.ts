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
  });
}
