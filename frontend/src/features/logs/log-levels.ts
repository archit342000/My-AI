/** Log levels: what a line or a row says about how serious it is. */
export type LogLevel = 'DEBUG' | 'INFO' | 'WARNING' | 'ERROR';

export const LOG_LEVELS: LogLevel[] = ['DEBUG', 'INFO', 'WARNING', 'ERROR'];

const LEVEL_RE = /\b(DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\b/;

/** Finds the level named in a log line. `WARN` and `CRITICAL` map to WARNING and ERROR. */
export function detectLevel(line: string): LogLevel | null {
  const match = LEVEL_RE.exec(line);
  if (!match) return null;
  const word = match[1]!;
  if (word === 'WARN') return 'WARNING';
  if (word === 'CRITICAL') return 'ERROR';
  return word as LogLevel;
}

/** Level of any entry: a line names it, an object carries it in `level` or `severity`. */
export function levelOf(entry: unknown): LogLevel | null {
  if (typeof entry === 'string') return detectLevel(entry);
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return null;
  const record = entry as Record<string, unknown>;
  const raw = record.level ?? record.severity;
  return typeof raw === 'string' ? detectLevel(raw.toUpperCase()) : null;
}

/** Cheap string hash (djb2) used to tell rows apart; not for security. */
function hash(text: string): string {
  let h = 5381;
  for (let i = 0; i < text.length; i++) h = ((h << 5) + h + text.charCodeAt(i)) | 0;
  return (h >>> 0).toString(36);
}

/**
 * Stable identity of a log row, so an expanded row stays the same row when the list refreshes and
 * rows are added at the top: its `id` when it has one, else its timestamp and log file, plus a hash
 * of the row's content.
 */
export function rowKey(entry: unknown): string {
  const json = typeof entry === 'string' ? entry : (JSON.stringify(entry) ?? '');
  if (entry && typeof entry === 'object' && !Array.isArray(entry)) {
    const row = entry as Record<string, unknown>;
    if (typeof row.id === 'string' || typeof row.id === 'number') return `id:${String(row.id)}`;
    const when = row.timestamp ?? row.time ?? row.ts ?? row.created_at;
    const file = row.log_file ?? row.file;
    if (when !== undefined) return `t:${String(when)}|${String(file ?? '')}|${hash(json)}`;
  }
  return `h:${hash(json)}`;
}

/**
 * Pairs each row with its key. Identical rows are told apart by their order counted from the end of
 * the list, so rows arriving in front of them (newest first) never move their keys. Known limit: when
 * the oldest of several identical id-less rows falls off the end of the row limit, the rest shift.
 */
export function rowKeys<T>(entries: T[]): Array<{ entry: T; key: string }> {
  const seen = new Map<string, number>();
  const keys = new Array<string>(entries.length);
  for (let i = entries.length - 1; i >= 0; i--) {
    const base = rowKey(entries[i]);
    const n = seen.get(base) ?? 0;
    seen.set(base, n + 1);
    keys[i] = n === 0 ? base : `${base}#${n}`;
  }
  return entries.map((entry, i) => ({ entry, key: keys[i] ?? '' }));
}

export type LogTone = 'neutral' | 'ok' | 'warn' | 'bad';

export interface LogSummary {
  /** Colour of the row's light: a problem, a warning, something that went well, or nothing to say. */
  tone: LogTone;
  /** When it happened, as given (shown as a time by the page); null when the entry has none. */
  when: string | number | null;
  /** The short name of the entry: its level, method, event or first value. */
  what: string;
  /** The rest of the line, cut by the page to one line. */
  detail: string;
  /** The chat the entry belongs to, when it names one. */
  chatId: string | null;
}

const TIME_KEYS = ['timestamp', 'time', 'ts', 'created_at'];
const LEVEL_KEYS = ['level', 'severity'];
const WHAT_KEYS = ['method', 'event', 'event_type', 'type', 'name', 'action'];

function toneOf(entry: unknown, level: LogLevel | null): LogTone {
  if (level === 'ERROR') return 'bad';
  if (level === 'WARNING') return 'warn';
  if (entry && typeof entry === 'object') {
    const row = entry as Record<string, unknown>;
    const status = Number(row.status ?? row.status_code);
    if (Number.isFinite(status) && status > 0) {
      if (status >= 500) return 'bad';
      if (status >= 400) return 'warn';
      if (status >= 200 && status < 300) return 'ok';
    }
    if (typeof row.error === 'string' && row.error) return 'bad';
  }
  return 'neutral';
}

/** A date and a time at the start of a text line, as loggers write them. */
const LINE_STAMP = /^\[?(\d{4}-\d{2}-\d{2})[ T](\d{2}:\d{2}:\d{2})(?:[.,]\d+)?\]?\s*/;
/** The level word of a text line with the separators around it. */
const LINE_LEVEL = /^[\s|:-]*\b(?:DEBUG|INFO|WARNING|WARN|ERROR|CRITICAL)\b[\s|:-]*/;

/** One line for a log entry: what the folded row shows before it is opened. */
export function logSummary(entry: unknown): LogSummary {
  const level = levelOf(entry);
  if (typeof entry === 'string') {
    const line = entry.split('\n')[0] ?? '';
    // "2026-11-11 04:52:07,142 | DEBUG | logger | message": the time and the level have their own places.
    const stamped = LINE_STAMP.exec(line);
    const rest = (stamped ? line.slice(stamped[0].length) : line)
      .replace(LINE_LEVEL, '')
      .replace(/^[\s|:-]+/, '');
    return {
      tone: toneOf(entry, level),
      when: stamped ? `${stamped[1]}T${stamped[2]}` : null,
      what: level ?? 'Line',
      detail: rest || line,
      chatId: null,
    };
  }
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) {
    return {
      tone: 'neutral',
      when: null,
      what: 'Entry',
      detail: JSON.stringify(entry) ?? '',
      chatId: null,
    };
  }
  const row = entry as Record<string, unknown>;
  const timeKey = TIME_KEYS.find((k) => typeof row[k] === 'string' || typeof row[k] === 'number');
  const when = timeKey ? (row[timeKey] as string | number) : null;
  const scalars = Object.entries(row).filter(
    ([key, value]) =>
      value !== null &&
      value !== '' &&
      ['string', 'number', 'boolean'].includes(typeof value) &&
      key !== timeKey &&
      !LEVEL_KEYS.includes(key),
  );
  const whatKey = WHAT_KEYS.find((k) => scalars.some(([key]) => key === k)) ?? scalars[0]?.[0];
  const what = level ?? (whatKey !== undefined ? String(row[whatKey]) : 'Entry');
  const detail = scalars
    .filter(([key]) => level !== null || key !== whatKey)
    .slice(0, 5)
    .map(([, value]) => String(value))
    .join(' · ');
  return {
    tone: toneOf(entry, level),
    when,
    what,
    detail,
    chatId: typeof row.chat_id === 'string' && row.chat_id ? row.chat_id : null,
  };
}
