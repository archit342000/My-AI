import { describe, expect, it } from 'vitest';
import {
  clockTime,
  dayGroup,
  daysAgo,
  durationLabel,
  fullDateTime,
  shortDate,
  toDate,
  whenLabel,
} from './format-time';

const NOW = new Date(2026, 10, 11, 15, 30); // 11 Nov 2026, 15:30

describe('toDate', () => {
  it('reads seconds, milliseconds and date strings; rejects what is not a date', () => {
    const ms = new Date(2026, 10, 11, 14, 2).getTime();
    expect(toDate(ms)?.getTime()).toBe(ms);
    expect(toDate(ms / 1000)?.getTime()).toBe(ms);
    expect(toDate(String(ms))?.getTime()).toBe(ms);
    expect(toDate('2026-11-03T09:40:00')?.getDate()).toBe(3);
    expect(toDate(null)).toBeNull();
    expect(toDate('')).toBeNull();
    expect(toDate('not a date')).toBeNull();
  });
});

describe('times and dates', () => {
  it('uses the 24-hour clock with two digits', () => {
    expect(clockTime(new Date(2026, 0, 5, 9, 4))).toBe('09:04');
    expect(clockTime(new Date(2026, 0, 5, 14, 2))).toBe('14:02');
  });

  it('writes the day before the month, with the year only when it differs', () => {
    expect(shortDate(new Date(2026, 10, 3), NOW)).toBe('3 Nov');
    expect(shortDate(new Date(2025, 10, 3), NOW)).toBe('3 Nov 2025');
    expect(fullDateTime(new Date(2026, 10, 3, 14, 2).getTime())).toBe('3 Nov 2026, 14:02');
    expect(fullDateTime(null)).toBe('');
  });

  it('counts calendar days, not 24-hour spans', () => {
    expect(daysAgo(new Date(2026, 10, 11, 0, 5), NOW)).toBe(0);
    expect(daysAgo(new Date(2026, 10, 10, 23, 55), NOW)).toBe(1);
  });
});

describe('whenLabel and dayGroup', () => {
  it('shows the time today, the weekday this week, the date before that', () => {
    expect(whenLabel(new Date(2026, 10, 11, 14, 2).getTime(), NOW)).toBe('14:02');
    expect(whenLabel(new Date(2026, 10, 9, 8, 0).getTime(), NOW)).toBe('Mon');
    expect(whenLabel(new Date(2026, 10, 3, 8, 0).getTime(), NOW)).toBe('3 Nov');
    expect(whenLabel(null, NOW)).toBe('');
  });

  it('groups today apart from everything earlier, undated rows included', () => {
    expect(dayGroup(new Date(2026, 10, 11, 0, 1).getTime(), NOW)).toBe('today');
    expect(dayGroup(new Date(2026, 10, 10, 23, 59).getTime(), NOW)).toBe('earlier');
    expect(dayGroup(null, NOW)).toBe('earlier');
  });
});

describe('durationLabel', () => {
  it('uses s, min and h with a space', () => {
    expect(durationLabel(46)).toBe('46 s');
    expect(durationLabel(125)).toBe('2 min 5 s');
    expect(durationLabel(120)).toBe('2 min');
    expect(durationLabel(3780)).toBe('1 h 3 min');
    expect(durationLabel(7200)).toBe('2 h');
    expect(durationLabel(-4)).toBe('0 s');
  });
});
