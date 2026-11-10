import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router';
import { PageTitle } from '../../app/PageTitle';
import { Icon } from '../../components/icons/Icon';
import { Button } from '../../components/ui/Button';
import { EmptyState } from '../../components/ui/EmptyState';
import { Input } from '../../components/ui/Field';
import { Notice } from '../../components/ui/Notice';
import { SegmentedControl } from '../../components/ui/SegmentedControl';
import { Select } from '../../components/ui/Select';
import { clockTime, fullDateTime, toDate } from '../../lib/format-time';
import { useIsAdmin } from '../../state/user-store';
import {
  LOG_LEVELS,
  levelOf,
  logSummary,
  rowKeys,
  type LogLevel,
  type LogTone,
} from './log-levels';
import { logsApi, toEntries, type LogStream } from './logsApi';

const LIMITS = [50, 100, 200, 500];
const MAX_CHARS = 4000;

const STREAMS: Array<{ value: LogStream; label: string }> = [
  { value: 'network', label: 'Network' },
  { value: 'events', label: 'Events' },
  { value: 'app', label: 'App' },
  { value: 'database', label: 'Database' },
];

const LEVEL_NAME: Record<LogLevel, string> = {
  DEBUG: 'Debug',
  INFO: 'Info',
  WARNING: 'Warning',
  ERROR: 'Error',
};

const TONE_CLASS: Record<LogTone, string | undefined> = {
  neutral: 'off',
  ok: 'ok',
  warn: 'warn',
  bad: 'bad',
};

/** Logs: network calls, events, app log lines and database rows. Admin only. */
export function LogsPage() {
  const isAdmin = useIsAdmin();
  // The content is a separate component so none of its queries are even created for a user.
  return isAdmin ? (
    <LogsContent />
  ) : (
    <EmptyState
      className="logs-denied"
      icon="lock"
      title="Not available"
      description="The logs are only available to the administrator."
    />
  );
}

function LogsContent() {
  const [stream, setStream] = useState<LogStream>('network');
  const [limit, setLimit] = useState(100);
  const [filter, setFilter] = useState('');
  const [table, setTable] = useState('chats');
  const [chatId, setChatId] = useState('');
  const [levels, setLevels] = useState<Set<LogLevel>>(new Set());
  // Rows are open by their stable key, not their position: the list refreshes every few seconds.
  const [open, setOpen] = useState<Set<string>>(new Set());

  const tables = useQuery({
    queryKey: ['log-tables'],
    queryFn: logsApi.dbTables,
    enabled: stream === 'database',
  });
  const data = useQuery({
    queryKey: ['logs', stream, limit, table, chatId],
    queryFn: async () => {
      if (stream === 'database') return logsApi.dbRows(table, chatId, limit);
      return logsApi.stream(stream, limit);
    },
    enabled: stream !== 'database' || Boolean(chatId),
    refetchInterval: 5000,
  });

  // The database log waits until a chat id is typed; that is not a loading state.
  const awaitingChatId = stream === 'database' && !chatId;
  const entries = useMemo(() => toEntries(data.data), [data.data]);
  const visible = useMemo(() => {
    const q = filter.trim().toLowerCase();
    return entries.filter((e) => {
      if (stream === 'app' && levels.size > 0) {
        const level = levelOf(e);
        if (!level || !levels.has(level)) return false;
      }
      return !q || (typeof e === 'string' ? e : JSON.stringify(e)).toLowerCase().includes(q);
    });
  }, [entries, filter, levels, stream]);
  const rows = useMemo(() => rowKeys(visible), [visible]);

  function toggle<T>(set: Set<T>, value: T): Set<T> {
    const next = new Set(set);
    if (next.has(value)) next.delete(value);
    else next.add(value);
    return next;
  }

  const filtering = filter.trim() !== '' || (stream === 'app' && levels.size > 0);

  return (
    <div className="logs-page">
      <PageTitle>Logs</PageTitle>
      <div className="logs-tools">
        <SegmentedControl
          label="Which log"
          value={stream}
          onChange={(v) => {
            setStream(v as LogStream);
            setOpen(new Set());
          }}
          options={STREAMS}
        />
        <Input
          type="search"
          aria-label="Filter entries"
          placeholder="Filter entries"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          className="logs-filter"
        />
        <Select
          aria-label="How many to load"
          className="logs-limit"
          value={String(limit)}
          onChange={(v) => setLimit(Number(v))}
          options={LIMITS.map((n) => ({ value: String(n), label: `Last ${n}` }))}
        />
        <Button
          variant="secondary"
          disabled={awaitingChatId}
          loading={data.isRefetching && !data.isPending}
          onClick={() => void data.refetch()}
        >
          <Icon name="refresh-cw" size={16} />
          Refresh
        </Button>
      </div>

      {stream === 'database' ? (
        <div className="logs-tools">
          <Select
            aria-label="Table"
            className="logs-table-pick"
            value={table}
            onChange={setTable}
            options={[
              ...(tables.data?.chat_tables ?? []),
              ...(tables.data?.global_tables ?? []),
            ].map((t) => ({ value: t, label: t }))}
          />
          <Input
            aria-label="Chat id"
            placeholder="Chat id"
            value={chatId}
            onChange={(e) => setChatId(e.target.value)}
            className="logs-chat-id"
          />
        </div>
      ) : null}

      {stream === 'app' ? (
        <div className="logs-levels" role="group" aria-label="Show only these levels">
          {LOG_LEVELS.map((level) => (
            <button
              key={level}
              type="button"
              className="ui-chip logs-level"
              aria-pressed={levels.has(level)}
              onClick={() => setLevels((s) => toggle(s, level))}
            >
              {LEVEL_NAME[level]}
            </button>
          ))}
        </div>
      ) : null}

      {awaitingChatId ? (
        <EmptyState
          icon="database"
          title="Enter a chat id"
          description="Database rows are loaded one chat at a time."
        />
      ) : data.isError ? (
        <Notice tone="bad" actionLabel="Try again" onAction={() => void data.refetch()}>
          The log could not be loaded. {data.error.message}
        </Notice>
      ) : data.isPending ? (
        <div className="loglist" role="status" aria-label="Loading the log">
          {Array.from({ length: 6 }, (_, i) => (
            <div key={i} className="log-row log-row--placeholder" aria-hidden="true" />
          ))}
        </div>
      ) : visible.length === 0 ? (
        <EmptyState
          icon="list"
          title={entries.length === 0 ? 'Nothing logged yet' : 'Nothing matches'}
          description={
            entries.length === 0
              ? 'Entries show up here as they are recorded.'
              : 'Try other words, or switch the level filters off.'
          }
        />
      ) : (
        <ol className="loglist">
          {rows.map(({ entry, key }) => {
            const summary = logSummary(entry);
            const isOpen = open.has(key);
            const text = typeof entry === 'string' ? entry : (JSON.stringify(entry, null, 2) ?? '');
            const date = toDate(summary.when);
            return (
              <li key={key} className={isOpen ? 'log-row log-row--open' : 'log-row'}>
                <button
                  type="button"
                  className="log-row__head"
                  aria-expanded={isOpen}
                  onClick={() => setOpen((s) => toggle(s, key))}
                >
                  <Icon name="chevron-right" size={14} className="log-row__chevron" />
                  <span className={`led ${TONE_CLASS[summary.tone] ?? ''}`} aria-hidden="true" />
                  {date ? (
                    <time className="dat keep" title={fullDateTime(summary.when)}>
                      {clockTime(date)}
                    </time>
                  ) : null}
                  <span className="log-row__what">{summary.what}</span>
                  <span className="log-row__detail">{summary.detail}</span>
                </button>
                {isOpen ? (
                  <div className="log-row__body">
                    <pre className="logs-json" tabIndex={0}>
                      {text.length > MAX_CHARS
                        ? `${text.slice(0, MAX_CHARS)}\n… (${Math.round(text.length / 1024)} KB in all)`
                        : text}
                    </pre>
                    {summary.chatId ? (
                      <Link
                        className="ui-button ui-button--link"
                        to={`/chat/${encodeURIComponent(summary.chatId)}`}
                      >
                        Open the chat
                      </Link>
                    ) : null}
                  </div>
                ) : null}
              </li>
            );
          })}
        </ol>
      )}

      {!awaitingChatId && !data.isError && !data.isPending && entries.length > 0 ? (
        <p className="ui-hint logs-count" role="status">
          {filtering
            ? `${visible.length} of ${entries.length} entries`
            : `${entries.length} ${entries.length === 1 ? 'entry' : 'entries'}`}
        </p>
      ) : null}
    </div>
  );
}
