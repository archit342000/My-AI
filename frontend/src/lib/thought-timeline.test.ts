import { describe, expect, it } from 'vitest';
import type { Step } from './chat-model';
import { statusOf, timelineOf } from './thought-timeline';

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
    expect(items.map((i) => i.kind)).toEqual(['reasoning', 'call', 'result', 'reasoning', 'event']);
  });

  it('leaves the main agent text out: it is the bubble', () => {
    expect(timelineOf([reasoning('a'), text('The answer')]).map((i) => i.kind)).toEqual([
      'reasoning',
    ]);
  });

  it('gives a tool with a result a call and a result entry, and a running tool only the call', () => {
    const [call, result] = timelineOf([tool('t', 'done')]);
    expect(call).toMatchObject({ kind: 'call', name: 't', running: false });
    expect(result).toMatchObject({ kind: 'result', name: 't', result: 'done' });
    expect(timelineOf([tool('t', null)])).toEqual([
      expect.objectContaining({ kind: 'call', running: true }),
    ]);
  });

  it('keeps an empty-string result as a result', () => {
    expect(timelineOf([tool('t', '')]).map((i) => i.kind)).toEqual(['call', 'result']);
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
      'call',
      'result',
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
