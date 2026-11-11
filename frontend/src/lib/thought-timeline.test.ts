import { describe, expect, it } from 'vitest';
import type { Step } from './chat-model';
import {
  statusOf,
  timelineOf,
  toolCount,
  toolDetail,
  toolFailed,
  toolSummary,
  type TimelineItem,
} from './thought-timeline';

const reasoning = (text: string, agent: string | null = null): Step => ({
  kind: 'reasoning',
  text,
  agent,
});
const text = (t: string, agent: string | null = null): Step => ({ kind: 'text', text: t, agent });
const event = (t: string): Step => ({ kind: 'event', text: t, agent: null });
const tool = (name: string, result: string | null, agent: string | null = null): Step => ({
  kind: 'tool',
  id: name,
  name,
  args: '{}',
  result,
  agent,
});

describe('timelineOf', () => {
  it('keeps the order of the steps', () => {
    const items = timelineOf([reasoning('a'), tool('web_search', 'r'), reasoning('b'), event('e')]);
    expect(items.map((i) => i.kind)).toEqual(['reasoning', 'tool', 'reasoning', 'event']);
  });

  it('leaves the main agent text out: it is the bubble', () => {
    expect(timelineOf([reasoning('a'), text('The answer')]).map((i) => i.kind)).toEqual([
      'reasoning',
    ]);
  });

  it('gives a tool one entry with its answer, and no answer while it runs', () => {
    expect(timelineOf([tool('t', 'done')])).toEqual([
      expect.objectContaining({ kind: 'tool', name: 't', result: 'done' }),
    ]);
    expect(timelineOf([tool('t', null)])).toEqual([
      expect.objectContaining({ kind: 'tool', result: null }),
    ]);
  });

  it('keeps an empty-string answer as an answer', () => {
    expect(timelineOf([tool('t', '')])).toEqual([expect.objectContaining({ result: '' })]);
  });

  it('groups consecutive steps of one sub-agent, labelled with its name', () => {
    const items = timelineOf([
      reasoning('main'),
      reasoning('sub', 'browsing_agent'),
      tool('open', 'page', 'browsing_agent'),
      text('found it', 'browsing_agent'),
      reasoning('back'),
    ]);
    expect(items.map((i) => i.kind)).toEqual(['reasoning', 'group', 'reasoning']);
    const group = items[1];
    expect(group).toMatchObject({ kind: 'group', label: 'Browsing agent' });
    expect(group?.kind === 'group' ? group.items.map((i) => i.kind) : []).toEqual([
      'reasoning',
      'tool',
      'text',
    ]);
  });

  it('starts a new group when another sub-agent follows, or the same one after main steps', () => {
    const items = timelineOf([
      reasoning('a', 'code_agent'),
      reasoning('b', 'file_agent'),
      reasoning('main'),
      reasoning('c', 'file_agent'),
    ]);
    expect(items.map((i) => i.kind)).toEqual(['group', 'group', 'reasoning', 'group']);
    expect(new Set(items.map((i) => i.key)).size).toBe(4);
  });

  it('skips empty steps and returns nothing for a turn with only text', () => {
    expect(timelineOf([reasoning(''), event('')])).toEqual([]);
    expect(timelineOf([text('hello')])).toEqual([]);
  });

  it('keeps keys stable when steps are appended', () => {
    const before = timelineOf([reasoning('a'), tool('t', null)]).map((i) => i.key);
    const after = timelineOf([reasoning('a'), tool('t', 'r'), reasoning('b')]).map((i) => i.key);
    expect(after.slice(0, before.length)).toEqual(before);
  });
});

describe('statusOf', () => {
  const label = (n: string) => `Label ${n}`;
  it('prefers the newest event', () => {
    expect(statusOf([event('first'), tool('t', null), event('second')], label)).toBe('second');
  });
  it('a tool that started after the newest event is the latest activity', () => {
    expect(statusOf([event('Searching'), tool('t', null)], label)).toBe('Label t');
    expect(statusOf([tool('t', null), event('Searching')], label)).toBe('Searching');
  });
  it('falls back to a running tool, then to nothing', () => {
    expect(statusOf([tool('a', 'x'), tool('b', null)], label)).toBe('Label b');
    expect(statusOf([tool('a', 'x'), reasoning('r')], label)).toBeNull();
  });
});

describe('toolCount and toolSummary', () => {
  const call = (key: string): TimelineItem => ({
    kind: 'tool',
    key,
    name: 't',
    args: '',
    result: '',
  });
  const items: TimelineItem[] = [
    { kind: 'reasoning', key: 'r', text: 'x' },
    call('a'),
    { kind: 'group', key: 'g', label: 'Research agent', items: [call('b'), call('c')] },
  ];

  it('counts calls, also inside sub-agent groups', () => {
    expect(toolCount(items)).toBe(3);
    expect(toolCount([])).toBe(0);
  });

  it('says it in words, singular and plural, and nothing when no tool was used', () => {
    expect(toolSummary(items)).toBe('3 tools used');
    expect(toolSummary([call('a')])).toBe('1 tool used');
    expect(toolSummary([{ kind: 'reasoning', key: 'r', text: 'x' }])).toBe('');
  });
});

describe('toolDetail', () => {
  it('gives the first plain value of the arguments, on one line', () => {
    expect(toolDetail('{"path":"tests/login.spec.ts","lines":3}')).toBe('tests/login.spec.ts');
    expect(toolDetail('{"deep":{"a":1},"count":20}')).toBe('20');
    expect(toolDetail('{"code":"print(1)\\nprint(2)"}')).toBe('print(1)');
  });

  it('is empty for no arguments, or ones still arriving', () => {
    expect(toolDetail('{}')).toBe('');
    expect(toolDetail('{"path":"te')).toBe('');
    expect(toolDetail('')).toBe('');
    expect(toolDetail('[1,2]')).toBe('');
    expect(toolDetail('null')).toBe('');
  });
});

describe('toolFailed', () => {
  it('reads the usual failure wording, and nothing else', () => {
    expect(toolFailed('Error: no network')).toBe(true);
    expect(toolFailed('{"error": "bad path"}')).toBe(true);
    expect(toolFailed('3 files, 0 errors')).toBe(false);
    expect(toolFailed('')).toBe(false);
    expect(toolFailed(null)).toBe(false);
  });
});
