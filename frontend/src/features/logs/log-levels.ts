/** Log levels shown as coloured badges in the app stream (plan F-50). */
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

/** Plain-object entries become table rows; scalar values become columns (at most `max`). */
export function scalarColumns(entries: unknown[], max = 6): string[] {
  const seen: string[] = [];
  for (const entry of entries) {
    if (!entry || typeof entry !== 'object' || Array.isArray(entry)) continue;
    for (const [key, value] of Object.entries(entry as Record<string, unknown>)) {
      const scalar = value === null || ['string', 'number', 'boolean'].includes(typeof value);
      if (scalar && !seen.includes(key)) seen.push(key);
      if (seen.length >= max) return seen;
    }
  }
  return seen;
}

/** Level of any entry: a line names it, an object carries it in `level` or `severity`. */
export function levelOf(entry: unknown): LogLevel | null {
  if (typeof entry === 'string') return detectLevel(entry);
  if (!entry || typeof entry !== 'object' || Array.isArray(entry)) return null;
  const record = entry as Record<string, unknown>;
  const raw = record.level ?? record.severity;
  return typeof raw === 'string' ? detectLevel(raw.toUpperCase()) : null;
}

const ACRONYMS = new Set(['id', 'url', 'ip', 'api', 'http', 'pdf', 'sql', 'uuid']);

/** Friendly column header: `chat_id` becomes "Chat ID", `status_code` becomes "Status Code". */
export function columnLabel(key: string): string {
  return key
    .split(/[_\s]+/)
    .filter(Boolean)
    .map((word) => {
      const lower = word.toLowerCase();
      return ACRONYMS.has(lower) ? lower.toUpperCase() : lower[0]!.toUpperCase() + lower.slice(1);
    })
    .join(' ');
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
