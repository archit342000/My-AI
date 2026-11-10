import { apiJson } from '../../api/client';

export type LogStream = 'network' | 'events' | 'app' | 'database';

export const logsApi = {
  stream: (stream: Exclude<LogStream, 'database'>, limit: number) => {
    const path =
      stream === 'network'
        ? '/api/logs'
        : stream === 'events'
          ? '/api/logs/events'
          : '/api/logs/app';
    return apiJson<unknown>(`${path}?limit=${limit}`);
  },
  dbTables: () =>
    apiJson<{ chat_tables: string[]; global_tables: string[] }>('/api/logs/db/tables'),
  dbRows: (table: string, chatId: string, limit: number) =>
    apiJson<unknown>(
      `/api/logs/db/table/${encodeURIComponent(table)}?chat_id=${encodeURIComponent(chatId)}&limit=${limit}`,
    ),
};

/** Turns a payload into a list of entries. Arrays pass through; `{logs|rows|...}` objects use their first array. */
export function toEntries(payload: unknown): unknown[] {
  if (Array.isArray(payload)) return payload;
  if (payload && typeof payload === 'object') {
    for (const v of Object.values(payload as Record<string, unknown>)) {
      if (Array.isArray(v)) return v;
    }
  }
  return [];
}
