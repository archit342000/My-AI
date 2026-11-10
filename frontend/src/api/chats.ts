import { apiJson, apiRequest } from './client';
import type { ChatDetail, ChatSummary, Workspace } from './types';

export interface ChatPatch {
  title?: string;
  user_preferences?: boolean;
  research_mode?: number;
  folder?: string | null;
  workspace_id?: string | null;
  file_system_mode?: number;
  browsing_mode?: number;
  git_mode?: number;
  code_execution_mode?: number;
  thinking_profile?: string;
  last_model?: string;
  resume_suppressed?: number;
}

const enc = encodeURIComponent;

export const chatsApi = {
  list: () => apiJson<ChatSummary[]>('/api/chats'),
  get: (chatId: string) => apiJson<ChatDetail>(`/api/chats/${enc(chatId)}`),
  listWorkspaces: () => apiJson<Workspace[]>('/api/chats/workspaces'),
  patch: (chatId: string, body: ChatPatch) =>
    apiJson<unknown>(`/api/chats/${enc(chatId)}`, { method: 'PATCH', json: body }),
  remove: (chatId: string) => apiRequest(`/api/chats/${enc(chatId)}`, { method: 'DELETE' }),
  stop: (chatId: string) => apiRequest(`/api/chats/${enc(chatId)}/stop`, { method: 'POST' }),
  editMessage: (chatId: string, messageId: string, content: string) =>
    apiJson<unknown>(`/api/chats/${enc(chatId)}/messages/${enc(messageId)}`, {
      method: 'PUT',
      json: { content },
    }),
  deleteMessage: (chatId: string, messageId: string) =>
    apiRequest(`/api/chats/${enc(chatId)}/messages/${enc(messageId)}`, { method: 'DELETE' }),
  discard: (chatId: string) => apiRequest(`/api/chats/${enc(chatId)}/discard`, { method: 'POST' }),
  createWorkspace: (name: string) =>
    apiJson<Workspace>('/api/chats/workspaces', { method: 'POST', json: { name } }),
  setWorkspaceIcon: (id: string, icon: string | null) =>
    apiJson<unknown>(`/api/chats/workspaces/${enc(id)}`, { method: 'PATCH', json: { icon } }),
  renameWorkspace: (id: string, name: string) =>
    apiJson<unknown>(`/api/chats/workspaces/${enc(id)}`, { method: 'PATCH', json: { name } }),
  deleteWorkspace: (id: string) =>
    apiRequest(`/api/chats/workspaces/${enc(id)}`, { method: 'DELETE' }),
  bulkDelete: () => apiRequest('/api/chats', { method: 'DELETE' }),
};

export const queryKeys = {
  chats: ['chats'] as const,
  chat: (id: string) => ['chat', id] as const,
  workspaces: ['workspaces'] as const,
  models: ['models'] as const,
};
