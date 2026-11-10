import { Fragment, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { EmptyState } from '../../components/ui/EmptyState';
import { Select } from '../../components/ui/Select';
import { Input } from '../../components/ui/Field';
import { Button } from '../../components/ui/Button';
import { Badge, type BadgeTone } from '../../components/ui/Badge';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { logsApi, toEntries, type LogStream } from './logsApi';
import { useIsAdmin } from '../../state/user-store';
import { LOG_LEVELS, columnLabel, levelOf, rowKeys, scalarColumns, type LogLevel } from './log-levels';

const LIMITS = [50, 100, 200, 500];
const MAX_CHARS = 4000;

const STREAMS: Array<{ value: LogStream; label: string }> = [
  { value: 'network', label: 'Network' },
  { value: 'events', label: 'Events' },
  { value: 'app', label: 'App logs' },
  { value: 'database', label: 'Database' },
];

const LEVEL_TONE: Record<LogLevel, BadgeTone> = {
  DEBUG: 'neutral',
  INFO: 'accent',
  WARNING: 'warning',
  ERROR: 'danger',
};

/** Logs viewer: network calls, events, app log lines and database rows. Admin only; large entries are truncated. */
export function LogsPage() {
  const isAdmin = useIsAdmin();
  // The content is a separate component so none of its queries are even created for a user.
  return isAdmin ? (
    <LogsContent />
  ) : (
    <EmptyState icon="info" title="Not available" description="The logs are only available to the administrator." />
  );
}

function LogsContent() {
  const [stream, setStream] = useState<LogStream>('network');
  const [limit, setLimit] = useState(100);
  const [filter, setFilter] = useState('');
  const [table, setTable] = useState('chats');
  const [chatId, setChatId] = useState('');
  const [levels, setLevels] = useState<Set<LogLevel>>(new Set());
  // Rows are expanded by their stable key, not their position: the list refreshes every few seconds.
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

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

  // The database stream stays disabled until a chat id is typed; that is not a loading state (F-04).
  const awaitingChatId = stream === 'database' && !chatId;
  const entries = useMemo(() => toEntries(data.data), [data.data]);
  const columns = useMemo(() => scalarColumns(entries), [entries]);
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return entries.filter((e) => {
      if (stream === 'app' && levels.size > 0) {
        const level = levelOf(e);
        if (!level || !levels.has(level)) return false;
      }
      return !q || JSON.stringify(e).toLowerCase().includes(q);
    });
  }, [entries, filter, levels, stream]);

  function toggleExpanded(key: string) {
    setExpanded((s) => {
      const n = new Set(s);
      if (n.has(key)) n.delete(key);
      else n.add(key);
      return n;
    });
  }

  function toggleLevel(level: LogLevel) {
    setLevels((s) => {
      const n = new Set(s);
      if (n.has(level)) n.delete(level);
      else n.add(level);
      return n;
    });
  }

  const rows = useMemo(() => rowKeys(visible), [visible]);
  const isTable = stream === 'network' || stream === 'events' || stream === 'database';

  /** Chat ids link to the chat; a `level` column gets the coloured badge. */
  function renderCell(column: string, row: Record<string, unknown>) {
    const value = row[column];
    const text = value === null || value === undefined ? '' : String(value);
    if (column === 'chat_id' && text) {
      return (
        <Link to={`/chat/${encodeURIComponent(text)}`} onClick={(e) => e.stopPropagation()}>
          {text}
        </Link>
      );
    }
    if (column === 'level') {
      const level = levelOf(row);
      if (level) return <Badge tone={LEVEL_TONE[level]}>{level}</Badge>;
    }
    return text;
  }

  return (
    <div className="logs-page">
      <div className="logs-main">
        <header className="logs-toolbar">
          <h1 className="font-heading logs-title">Logs</h1>
          <SegmentedControl label="Log stream" value={stream} onChange={(v) => { setStream(v as LogStream); setExpanded(new Set()); }} options={STREAMS} />
          <div className="logs-toolbar__controls">
            <Select aria-label="Rows" value={String(limit)} onChange={(v) => setLimit(Number(v))} options={LIMITS.map((n) => ({ value: String(n), label: `${n} rows` }))} />
            <Input aria-label="Filter entries" placeholder="Filter…" value={filter} onChange={(e) => setFilter(e.target.value)} className="logs-filter" />
            <Button variant="secondary" disabled={awaitingChatId} onClick={() => void data.refetch()}>Refresh</Button>
          </div>
        </header>

        {stream === 'database' ? (
          <div className="logs-toolbar__controls">
            <Select
              aria-label="Table"
              value={table}
              onChange={setTable}
              options={[...(tables.data?.chat_tables ?? []), ...(tables.data?.global_tables ?? [])].map((t) => ({ value: t, label: t }))}
            />
            <Input aria-label="Chat id" placeholder="chat id" value={chatId} onChange={(e) => setChatId(e.target.value)} className="logs-chat-id" />
          </div>
        ) : null}

        {stream === 'app' ? (
          <div className="logs-levels" role="group" aria-label="Filter by level">
            {LOG_LEVELS.map((level) => (
              <button key={level} type="button" className="logs-level-chip" aria-pressed={levels.has(level)} onClick={() => toggleLevel(level)}>
                <Badge tone={LEVEL_TONE[level]}>{level}</Badge>
              </button>
            ))}
          </div>
        ) : null}

        <div className="logs-status">
          {awaitingChatId || data.isError || (!data.isPending && entries.length === 0)
            ? ''
            : data.isPending
              ? 'Loading…'
              : `${visible.length} of ${entries.length} entries`}
        </div>

        {awaitingChatId ? (
          <EmptyState title="Enter a chat id to load rows" description="Database rows are loaded per chat." />
        ) : data.isError ? (
          <EmptyState icon="error" title="Could not load logs" description={data.error.message} />
        ) : !data.isPending && visible.length === 0 ? (
          <EmptyState
            icon="logs"
            title={entries.length === 0 ? 'No entries yet' : 'No entries match'}
            description={
              entries.length === 0
                ? 'Nothing has been recorded for this stream.'
                : 'Try another filter or clear the level chips.'
            }
          />
        ) : isTable && typeof visible[0] === 'object' ? (
          <div className="logs-table-wrap">
            <table className="logs-table">
              <thead>
                <tr>
                  {columns.map((c) => <th key={c} scope="col">{columnLabel(c)}</th>)}
                </tr>
              </thead>
              <tbody>
                {rows.map(({ entry, key }) => {
                  const row = (entry ?? {}) as Record<string, unknown>;
                  const json = JSON.stringify(entry, null, 2) ?? '';
                  const isOpen = expanded.has(key);
                  return (
                    <Fragment key={key}>
                      <tr className="logs-row" aria-expanded={isOpen} onClick={() => toggleExpanded(key)}>
                        {columns.map((c) => (
                          <td key={c} title={String(row[c] ?? '')}>
                            {renderCell(c, row)}
                          </td>
                        ))}
                      </tr>
                      {isOpen ? (
                        <tr className="logs-row-detail">
                          <td colSpan={Math.max(columns.length, 1)}>
                            <pre className="logs-json">{json.length > MAX_CHARS ? `${json.slice(0, MAX_CHARS)}\n…` : json}</pre>
                          </td>
                        </tr>
                      ) : null}
                    </Fragment>
                  );
                })}
              </tbody>
            </table>
          </div>
        ) : (
          <ol className="logs-list">
            {rows.map(({ entry, key }) => {
              const text = typeof entry === 'string' ? entry : JSON.stringify(entry, null, 2) ?? '';
              const isOpen = expanded.has(key);
              const level = levelOf(entry);
              const shown = isOpen || text.length <= MAX_CHARS ? text : `${text.slice(0, MAX_CHARS)}\n…`;
              return (
                <li key={key} className="logs-entry">
                  {level ? <Badge tone={LEVEL_TONE[level]}>{level}</Badge> : null}
                  <pre className="logs-json">{shown}</pre>
                  {text.length > MAX_CHARS ? (
                    <Button variant="ghost" size="sm" onClick={() => toggleExpanded(key)}>
                      {isOpen ? 'Collapse' : `Show all (${Math.round(text.length / 1024)} KB)`}
                    </Button>
                  ) : null}
                </li>
              );
            })}
          </ol>
        )}
      </div>
    </div>
  );
}
