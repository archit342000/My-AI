import { describe, expect, it } from 'vitest';
import { columnLabel, detectLevel, levelOf, rowKey, rowKeys, scalarColumns } from './log-levels';

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

describe('rowKey', () => {
  it('is stable for the same row and differs for different rows', () => {
    const a = { timestamp: '2026-11-10T10:00:00', url: '/api/a', status: 200 };
    const b = { timestamp: '2026-11-10T10:00:00', url: '/api/b', status: 200 };
    expect(rowKey(a)).toBe(rowKey({ ...a }));
    expect(rowKey(a)).not.toBe(rowKey(b));
  });

  it('uses the id when a row has one', () => {
    expect(rowKey({ id: 7, message: 'x' })).toBe('id:7');
    expect(rowKey({ id: 7, message: 'changed' })).toBe('id:7');
  });

  it('keys plain log lines by their content', () => {
    expect(rowKey('INFO started')).toBe(rowKey('INFO started'));
    expect(rowKey('INFO started')).not.toBe(rowKey('INFO stopped'));
  });

  it('rowKeys tells identical rows apart and keeps keys when rows are added in front', () => {
    const row = { timestamp: 't1', url: '/same' };
    const keys = rowKeys([row, row]).map((r) => r.key);
    expect(new Set(keys).size).toBe(2);
    const fresh = { timestamp: 't2', url: '/new' };
    expect(rowKeys([fresh, row, row]).map((r) => r.key).slice(1)).toEqual(keys);
    // an identical row arriving in front of the older ones must not move their keys either
    expect(rowKeys([row, row, row]).map((r) => r.key).slice(1)).toEqual(keys);
  });

  it('rowKeys pairs each entry with its key', () => {
    const a = { id: 1 };
    const b = { id: 2 };
    expect(rowKeys([a, b])).toEqual([
      { entry: a, key: 'id:1' },
      { entry: b, key: 'id:2' },
    ]);
  });
});
