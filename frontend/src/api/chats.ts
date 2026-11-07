import { apiJson } from './client';
import type { ChatDetail, ChatSummary, Workspace } from './types';

export const chatsApi = {
  list: () => apiJson<ChatSummary[]>('/api/chats'),
  get: (chatId: string) => apiJson<ChatDetail>(`/api/chats/${encodeURIComponent(chatId)}`),
  listWorkspaces: () => apiJson<Workspace[]>('/api/chats/workspaces'),
};

export const queryKeys = {
  chats: ['chats'] as const,
  chat: (id: string) => ['chat', id] as const,
  workspaces: ['workspaces'] as const,
};
