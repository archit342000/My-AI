import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { logsApi, toEntries, type LogStream } from './logsApi';

const LIMITS = [50, 100, 200, 500];
const MAX_CHARS = 4000;

const STREAMS: Array<[LogStream, string]> = [
  ['network', 'Network'],
  ['events', 'Events'],
  ['app', 'App logs'],
  ['database', 'Database'],
];

/** Logs viewer: network calls, events, app log lines and database rows. Large entries are truncated. */
export function LogsPage() {
  const [stream, setStream] = useState<LogStream>('network');
  const [limit, setLimit] = useState(100);
  const [filter, setFilter] = useState('');
  const [table, setTable] = useState('chats');
  const [chatId, setChatId] = useState('');
  const [expanded, setExpanded] = useState<Set<number>>(new Set());

  const tables = useQuery({ queryKey: ['log-tables'], queryFn: logsApi.dbTables, enabled: stream === 'database' });
  const data = useQuery({
    queryKey: ['logs', stream, limit, table, chatId],
    queryFn: async () => {
      if (stream === 'database') return logsApi.dbRows(table, chatId, limit);
      return logsApi.stream(stream, limit);
    },
    enabled: stream !== 'database' || Boolean(chatId),
    refetchInterval: 5000,
  });

  const entries = useMemo(() => toEntries(data.data), [data.data]);
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    if (!q) return entries;
    return entries.filter((e) => JSON.stringify(e).toLowerCase().includes(q));
  }, [entries, filter]);

  return (
    <div className="logs-page" style={{ display: 'flex', height: '100vh', paddingLeft: 280, boxSizing: 'border-box' }}>
      <div style={{ flex: 1, minWidth: 0, display: 'flex', flexDirection: 'column', padding: 16, gap: 12 }}>
        <header style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <h1 className="font-heading" style={{ fontSize: '1.25rem', margin: 0, marginRight: 12 }}>Logs</h1>
          {STREAMS.map(([key, label]) => (
            <button key={key} type="button" aria-pressed={stream === key} className={stream === key ? 'btn-primary' : 'btn-secondary'} onClick={() => { setStream(key); setExpanded(new Set()); }}>{label}</button>
          ))}
          <select aria-label="Rows" value={limit} onChange={(e) => setLimit(Number(e.target.value))} style={{ padding: 6, borderRadius: 8 }}>
            {LIMITS.map((n) => <option key={n} value={n}>{n} rows</option>)}
          </select>
          <input aria-label="Filter entries" placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} style={{ flex: 1, minWidth: 160, padding: 6, borderRadius: 8, border: '1px solid var(--glass-border)', background: 'var(--glass-surface)', color: 'var(--content-primary)' }} />
          <button type="button" className="btn-ghost" onClick={() => void data.refetch()}>Refresh</button>
        </header>

        {stream === 'database' ? (
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <select aria-label="Table" value={table} onChange={(e) => setTable(e.target.value)} style={{ padding: 6, borderRadius: 8 }}>
              {[...(tables.data?.chat_tables ?? []), ...(tables.data?.global_tables ?? [])].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            <input aria-label="Chat id" placeholder="chat id" value={chatId} onChange={(e) => setChatId(e.target.value)} style={{ padding: 6, borderRadius: 8, minWidth: 220 }} />
          </div>
        ) : null}

        <div style={{ fontSize: '0.8rem', color: 'var(--content-muted)' }}>
          {data.isPending ? 'Loading…' : data.isError ? `Error: ${data.error.message}` : `${visible.length} of ${entries.length} entries`}
        </div>

        <ol style={{ listStyle: 'none', margin: 0, padding: 0, flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 6 }}>
          {visible.map((entry, i) => {
            const text = JSON.stringify(entry, null, 2) ?? '';
            const isOpen = expanded.has(i);
            const shown = isOpen || text.length <= MAX_CHARS ? text : `${text.slice(0, MAX_CHARS)}\n…`;
            return (
              <li key={i} className="glass" style={{ borderRadius: 10, padding: 8 }}>
                <pre className="font-mono" style={{ margin: 0, whiteSpace: 'pre-wrap', wordBreak: 'break-word', fontSize: '0.75rem' }}>{typeof entry === 'string' ? entry : shown}</pre>
                {text.length > MAX_CHARS ? (
                  <button type="button" className="btn-ghost" onClick={() => setExpanded((s) => { const n = new Set(s); if (n.has(i)) n.delete(i); else n.add(i); return n; })}>
                    {isOpen ? 'Collapse' : `Show all (${Math.round(text.length / 1024)} KB)`}
                  </button>
                ) : null}
              </li>
            );
          })}
        </ol>
      </div>
    </div>
  );
}
