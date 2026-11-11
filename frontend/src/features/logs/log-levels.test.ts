import { describe, expect, it } from 'vitest';
import { detectLevel, levelOf, logSummary, rowKey, rowKeys } from './log-levels';

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

describe('levels of objects', () => {
  it('reads the level from an object field, case-insensitively', () => {
    expect(levelOf({ level: 'error', msg: 'x' })).toBe('ERROR');
    expect(levelOf({ severity: 'warn' })).toBe('WARNING');
    expect(levelOf({ msg: 'no level' })).toBeNull();
    expect(levelOf(['INFO'])).toBeNull();
    expect(levelOf('INFO started')).toBe('INFO');
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
    expect(
      rowKeys([fresh, row, row])
        .map((r) => r.key)
        .slice(1),
    ).toEqual(keys);
    // an identical row arriving in front of the older ones must not move their keys either
    expect(
      rowKeys([row, row, row])
        .map((r) => r.key)
        .slice(1),
    ).toEqual(keys);
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

describe('logSummary', () => {
  it('a text line shows its level and its first line, toned by the level', () => {
    expect(logSummary('ERROR could not reach the server\nretrying')).toEqual({
      tone: 'bad',
      when: null,
      what: 'ERROR',
      detail: 'could not reach the server',
      chatId: null,
    });
    // A line that starts with a date and time gives them to the row's time.
    expect(
      logSummary('2026-11-11 04:52:07,142 | DEBUG | backend.db | [DB CONNECTION] opened'),
    ).toEqual({
      tone: 'neutral',
      when: '2026-11-11T04:52:07',
      what: 'DEBUG',
      detail: 'backend.db | [DB CONNECTION] opened',
      chatId: null,
    });
    expect(logSummary('WARN slow').tone).toBe('warn');
    expect(logSummary('just text')).toMatchObject({
      tone: 'neutral',
      what: 'Line',
      detail: 'just text',
    });
  });

  it('a network row leads with its method, then the rest, toned by its status', () => {
    const row = {
      timestamp: '2026-11-10T14:01:31',
      method: 'POST',
      url: '/v1/chat',
      status: 200,
      chat_id: 'c1',
    };
    expect(logSummary(row)).toEqual({
      tone: 'ok',
      when: '2026-11-10T14:01:31',
      what: 'POST',
      detail: '/v1/chat · 200 · c1',
      chatId: 'c1',
    });
    expect(logSummary({ ...row, status: 404 }).tone).toBe('warn');
    expect(logSummary({ ...row, status: 502 }).tone).toBe('bad');
  });

  it('an event leads with its event name; a row with a level leads with the level', () => {
    expect(logSummary({ ts: 5, event: 'tool.finished', tool: 'web_search' })).toMatchObject({
      what: 'tool.finished',
      detail: 'web_search',
      when: 5,
    });
    expect(logSummary({ level: 'error', message: 'boom' })).toMatchObject({
      tone: 'bad',
      what: 'ERROR',
      detail: 'boom',
    });
  });

  it('a row without a known name leads with its first value; nested values are left to the opened row', () => {
    expect(logSummary({ id: 4, title: 'Fix the test', extra: { a: 1 }, empty: '' })).toMatchObject({
      what: '4',
      detail: 'Fix the test',
      tone: 'neutral',
    });
    expect(logSummary({ error: 'bad thing' }).tone).toBe('bad');
    expect(logSummary(42)).toMatchObject({ what: 'Entry', detail: '42' });
  });
});
