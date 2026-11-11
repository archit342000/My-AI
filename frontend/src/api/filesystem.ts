/** Artifact (file system) endpoints. Most take `chat_id` or `workspace_id` as a query or body field. */
import { apiJson, apiRequest } from './client';

export interface Artifact {
  id: string;
  filename: string;
  title: string;
  type: string;
  /** What the file is for the server: `custom`, or a research plan or report. */
  file_system_type?: string;
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

/** The server's comparison of two versions: the lines only in each, by position (`backend/file_system/manager.py`). */
export interface VersionDiff {
  added_lines: string[];
  removed_lines: string[];
  stats: { lines_added: number; lines_removed: number };
}

/** Scope as the version endpoints read it: `chat_id` in the body, `workspace_id` in the query only. */
function workspaceQuery(scope: ScopeRef): string {
  return scope.workspaceId ? `?workspace_id=${encodeURIComponent(scope.workspaceId)}` : '';
}

export const artifactsApi = {
  list: (scope: ScopeRef) =>
    apiJson<{ file_systems: Artifact[] }>(`/api/file_systems?${scopeQuery(scope)}`).then(
      (r) => r.file_systems,
    ),
  get: (id: string, scope: ScopeRef) =>
    apiJson<Artifact & { content: string }>(
      `/api/file_systems/${encodeURIComponent(id)}?${scopeQuery(scope)}`,
    ),
  create: (
    scope: ScopeRef,
    body: { title: string; content: string; language: string; folder?: string },
  ) =>
    apiJson<{ id: string }>('/api/file_systems', {
      method: 'POST',
      json: { ...scopeBody(scope), ...body },
    }),
  update: (
    id: string,
    scope: ScopeRef,
    body: { content?: string; title?: string; folder?: string },
    options: { keepalive?: boolean } = {},
  ) =>
    apiJson<unknown>(`/api/file_systems/${encodeURIComponent(id)}`, {
      method: 'PATCH',
      json: { ...scopeBody(scope), ...body },
      keepalive: options.keepalive,
    }),
  remove: (id: string, scope: ScopeRef) =>
    apiRequest(`/api/file_systems/${encodeURIComponent(id)}?${scopeQuery(scope)}`, {
      method: 'DELETE',
    }),
  versions: (id: string, scope: ScopeRef) =>
    apiJson<{ versions: ArtifactVersion[] }>(
      `/api/file_systems/${encodeURIComponent(id)}/versions?${scopeQuery(scope)}`,
    ).then((r) => r.versions),
  version: (id: string, n: number, scope: ScopeRef) =>
    apiJson<{ content: string }>(
      `/api/file_systems/${encodeURIComponent(id)}/versions/${n}?${scopeQuery(scope)}`,
    ),
  restore: (id: string, n: number, scope: ScopeRef) =>
    apiRequest(
      `/api/file_systems/${encodeURIComponent(id)}/versions/${n}/restore${workspaceQuery(scope)}`,
      {
        method: 'POST',
        json: scope.chatId ? { chat_id: scope.chatId } : {},
      },
    ),
  /** Version numbers differ in content: the lines only in `from` (removed) and only in `to` (added). */
  diff: (id: string, from: number, to: number, scope: ScopeRef) =>
    apiJson<VersionDiff>(
      `/api/file_systems/${encodeURIComponent(id)}/diff${workspaceQuery(scope)}`,
      {
        method: 'POST',
        json: { ...(scope.chatId ? { chat_id: scope.chatId } : {}), version1: from, version2: to },
      },
    ),
  currentVersion: (id: string, scope: ScopeRef) =>
    apiJson<{ current_version: number | null }>(
      `/api/file_systems/${encodeURIComponent(id)}/current-version?${scopeQuery(scope)}`,
    ).then((r) => r.current_version),
  createDirectory: (scope: ScopeRef, path: string) =>
    apiJson<unknown>('/api/file_systems/directory', {
      method: 'POST',
      json: { ...scopeBody(scope), path },
    }),
  /** Removes an empty directory; the server refuses a non-empty one with its own message. */
  deleteDirectory: (scope: ScopeRef, path: string) =>
    apiRequest(
      `/api/file_systems/directory?${scopeQuery(scope)}&path=${encodeURIComponent(path)}`,
      { method: 'DELETE' },
    ),
  exportUrl: (id: string, format: 'html' | 'markdown' | 'pdf', scope: ScopeRef) =>
    `/api/file_systems/${encodeURIComponent(id)}/export/${format}?${scopeQuery(scope)}`,
  rawUrl: (id: string, scope: ScopeRef) =>
    `/api/file_systems/${encodeURIComponent(id)}/raw?${scopeQuery(scope)}`,
  folders: (chatId: string) =>
    apiJson<{ folders: string[] }>(
      `/api/file_systems/chat/${encodeURIComponent(chatId)}/folders`,
    ).then((r) => r.folders),
};

/** The fields the history view reads from a `code_execution_history` row (backend/database/init_db.py), newest first. */
export interface CodeRun {
  id: string;
  chat_id: string;
  language: string;
  code: string;
  stdin: string | null;
  stdout: string | null;
  stderr: string | null;
  exit_code: number | null;
  execution_time_ms: number | null;
  timed_out: number | null;
  created_at: string | null;
}

export const codeExecApi = {
  history: (chatId: string) =>
    apiJson<CodeRun[]>(`/api/tools/code-execution/history/${encodeURIComponent(chatId)}`),
  /** Runs a saved file of the chat and returns what it printed (or the runner's own error text). */
  runFile: (chatId: string, path: string) =>
    apiJson<{ result: string }>('/api/tools/code-execution/run-file', {
      method: 'POST',
      json: { chat_id: chatId, path },
    }).then((r) => r.result),
};

export const portalApi = {
  init: () =>
    apiJson<{ url?: string; session_id?: string }>('/api/tools/portal/init', { method: 'POST' }),
};
