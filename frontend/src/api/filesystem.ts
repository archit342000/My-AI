/** Artifact (file system) endpoints. Most take `chat_id` or `workspace_id` as a query or body field. */
import { apiJson, apiRequest } from './client';

export interface Artifact {
  id: string;
  filename: string;
  title: string;
  type: string;
  folder?: string;
  language?: string;
  content?: string;
  tags?: string[];
  timestamp?: number;
}

export interface ArtifactVersion {
  version_number: number;
  author: string;
  timestamp: number;
  comment: string;
}

export interface ScopeRef {
  chatId?: string;
  workspaceId?: string;
}

/** Query-key part that identifies a chat or workspace scope. */
export const scopeKey = (s: ScopeRef) => `${s.chatId ?? ''}|${s.workspaceId ?? ''}`;

/** Query key of a scope's file list; invalidate it to refresh the files panel. */
export const artifactsKey = (s: ScopeRef) => ['artifacts', scopeKey(s)] as const;

function scopeQuery(scope: ScopeRef): string {
  const q = new URLSearchParams();
  if (scope.chatId) q.set('chat_id', scope.chatId);
  if (scope.workspaceId) q.set('workspace_id', scope.workspaceId);
  return q.toString();
}

function scopeBody(scope: ScopeRef): Record<string, string> {
  const body: Record<string, string> = {};
  if (scope.chatId) body.chat_id = scope.chatId;
  if (scope.workspaceId) body.workspace_id = scope.workspaceId;
  return body;
}

export const artifactsApi = {
  list: (scope: ScopeRef) =>
    apiJson<{ file_systems: Artifact[] }>(`/api/file_systems?${scopeQuery(scope)}`).then((r) => r.file_systems),
  get: (id: string, scope: ScopeRef) =>
    apiJson<Artifact & { content: string }>(`/api/file_systems/${encodeURIComponent(id)}?${scopeQuery(scope)}`),
  create: (scope: ScopeRef, body: { title: string; content: string; language: string; folder?: string }) =>
    apiJson<{ id: string }>('/api/file_systems', { method: 'POST', json: { ...scopeBody(scope), ...body } }),
  update: (id: string, scope: ScopeRef, body: { content?: string; title?: string; folder?: string }) =>
    apiJson<unknown>(`/api/file_systems/${encodeURIComponent(id)}`, { method: 'PATCH', json: { ...scopeBody(scope), ...body } }),
  remove: (id: string, scope: ScopeRef) =>
    apiRequest(`/api/file_systems/${encodeURIComponent(id)}?${scopeQuery(scope)}`, { method: 'DELETE' }),
  versions: (id: string, scope: ScopeRef) =>
    apiJson<{ versions: ArtifactVersion[] }>(`/api/file_systems/${encodeURIComponent(id)}/versions?${scopeQuery(scope)}`).then((r) => r.versions),
  version: (id: string, n: number, scope: ScopeRef) =>
    apiJson<{ content: string }>(`/api/file_systems/${encodeURIComponent(id)}/versions/${n}?${scopeQuery(scope)}`),
  restore: (id: string, n: number, scope: ScopeRef) =>
    apiRequest(`/api/file_systems/${encodeURIComponent(id)}/versions/${n}/restore`, { method: 'POST', json: scopeBody(scope) }),
  exportUrl: (id: string, format: 'html' | 'markdown' | 'pdf', scope: ScopeRef) =>
    `/api/file_systems/${encodeURIComponent(id)}/export/${format}?${scopeQuery(scope)}`,
  rawUrl: (id: string, scope: ScopeRef) => `/api/file_systems/${encodeURIComponent(id)}/raw?${scopeQuery(scope)}`,
  folders: (chatId: string) =>
    apiJson<{ folders: string[] }>(`/api/file_systems/chat/${encodeURIComponent(chatId)}/folders`).then((r) => r.folders),
};

export const codeExecApi = {
  history: (chatId: string) => apiJson<unknown[]>(`/api/tools/code-execution/history/${encodeURIComponent(chatId)}`),
};

export const portalApi = {
  init: () => apiJson<{ url?: string; session_id?: string }>('/api/tools/portal/init', { method: 'POST' }),
};
