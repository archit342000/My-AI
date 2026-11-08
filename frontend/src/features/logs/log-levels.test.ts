import { describe, expect, it } from 'vitest';
import { columnLabel, detectLevel, levelOf, scalarColumns } from './log-levels';

describe('log levels (F-50)', () => {
  it('finds the level word in a line', () => {
    expect(detectLevel('2026-11-08 12:00:00 INFO app started')).toBe('INFO');
    expect(detectLevel('DEBUG cache hit')).toBe('DEBUG');
    expect(detectLevel('something WARN happened')).toBe('WARNING');
    expect(detectLevel('CRITICAL disk full')).toBe('ERROR');
  });

  it('returns null when no level is present', () => {
    expect(detectLevel('plain text line')).toBeNull();
  });
});

describe('table columns (F-49)', () => {
  it('uses scalar keys only, in first-seen order, capped', () => {
    const columns = scalarColumns([
      { time: 1, category: 'chat', nested: { a: 1 }, type: 'x' },
      { time: 2, extra: true, more: 'y', nine: 9, ten: 10, eleven: 11, twelve: 12 },
    ]);
    expect(columns).toEqual(['time', 'category', 'type', 'extra', 'more', 'nine']);
  });

  it('ignores non-object entries', () => {
    expect(scalarColumns(['line one', null, [1, 2]])).toEqual([]);
  });
});

describe('object levels and headers (F-49, F-50)', () => {
  it('reads the level from an object field, case-insensitively', () => {
    expect(levelOf({ level: 'error', msg: 'x' })).toBe('ERROR');
    expect(levelOf({ severity: 'warn' })).toBe('WARNING');
    expect(levelOf({ msg: 'no level' })).toBeNull();
    expect(levelOf(['INFO'])).toBeNull();
    expect(levelOf('INFO started')).toBe('INFO');
  });

  it('title-cases keys and keeps known acronyms upper case', () => {
    expect(columnLabel('chat_id')).toBe('Chat ID');
    expect(columnLabel('status_code')).toBe('Status Code');
    expect(columnLabel('timestamp')).toBe('Timestamp');
  });
});

