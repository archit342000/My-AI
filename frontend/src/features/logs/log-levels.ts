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
