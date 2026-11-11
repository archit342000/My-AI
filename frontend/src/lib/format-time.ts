/**
 * Times and dates as the rule book writes them (Part 9): 24-hour times, day before month,
 * short and unambiguous.
 */

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
const DAYS = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];

/** Reads a timestamp given as seconds, milliseconds or a date string. Null when it is not a date. */
export function toDate(value: number | string | null | undefined): Date | null {
  if (value === null || value === undefined || value === '') return null;
  const numeric = typeof value === 'number' ? value : Number(value);
  const date = Number.isFinite(numeric)
    ? new Date(numeric < 1e12 ? numeric * 1000 : numeric)
    : new Date(String(value));
  return Number.isNaN(date.getTime()) ? null : date;
}

const two = (n: number) => String(n).padStart(2, '0');

/** 14:02 */
export function clockTime(date: Date): string {
  return `${two(date.getHours())}:${two(date.getMinutes())}`;
}

/** 3 Nov, or 3 Nov 2025 when it is not this year. */
export function shortDate(date: Date, now: Date = new Date()): string {
  const base = `${date.getDate()} ${MONTHS[date.getMonth()]}`;
  return date.getFullYear() === now.getFullYear() ? base : `${base} ${date.getFullYear()}`;
}

function startOfDay(date: Date): number {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
}

/** Whole days between two dates' calendar days (0 = the same day). */
export function daysAgo(date: Date, now: Date = new Date()): number {
  return Math.round((startOfDay(now) - startOfDay(date)) / 86_400_000);
}

/**
 * The short "when" beside a list row: the time today, the weekday within the last week,
 * otherwise the date. Empty when there is no date.
 */
export function whenLabel(
  value: number | string | null | undefined,
  now: Date = new Date(),
): string {
  const date = toDate(value);
  if (!date) return '';
  const days = daysAgo(date, now);
  if (days <= 0) return clockTime(date);
  if (days < 7) return DAYS[date.getDay()] ?? '';
  return shortDate(date, now);
}

/** 3 Nov 2026, 14:02 */
export function fullDateTime(value: number | string | null | undefined): string {
  const date = toDate(value);
  if (!date) return '';
  return `${date.getDate()} ${MONTHS[date.getMonth()]} ${date.getFullYear()}, ${clockTime(date)}`;
}

/** 46 s, 2 min 5 s, 1 h 3 min. */
export function durationLabel(seconds: number): string {
  const total = Math.max(0, Math.round(seconds));
  if (total < 60) return `${total} s`;
  const minutes = Math.floor(total / 60);
  if (minutes < 60) {
    const rest = total % 60;
    return rest ? `${minutes} min ${rest} s` : `${minutes} min`;
  }
  const hours = Math.floor(minutes / 60);
  const restMinutes = minutes % 60;
  return restMinutes ? `${hours} h ${restMinutes} min` : `${hours} h`;
}

export type DayGroup = 'today' | 'earlier';

/** Which list heading a row belongs under. A row with no date goes under Earlier. */
export function dayGroup(
  value: number | string | null | undefined,
  now: Date = new Date(),
): DayGroup {
  const date = toDate(value);
  return date && daysAgo(date, now) <= 0 ? 'today' : 'earlier';
}
