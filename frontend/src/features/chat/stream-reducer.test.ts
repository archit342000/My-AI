import { describe, expect, it } from 'vitest';
import { applyChunk, attachResult, emptyLiveTurn, mergeToolCalls, StreamError } from './stream-reducer';

const delta = (d: Record<string, unknown>, extra: Record<string, unknown> = {}) => ({ choices: [{ delta: d }], ...extra });

describe('applyChunk', () => {
  it('accumulates content and reasoning', () => {
    let t = emptyLiveTurn();
    t = applyChunk(t, delta({ content: 'Hel' }));
    t = applyChunk(t, delta({ content: 'lo' }));
    t = applyChunk(t, delta({ reasoning_content: 'think' }));
    expect(t.content).toBe('Hello');
    expect(t.reasoning).toBe('think');
  });

  it('records the model name', () => {
    expect(applyChunk(emptyLiveTurn(), { model: 'gemma' }).model).toBe('gemma');
  });

  it('throws on an error chunk', () => {
    expect(() => applyChunk(emptyLiveTurn(), { error: 'boom' })).toThrow(StreamError);
  });

  it('counts sub-agent deltas without touching main content', () => {
    const t = applyChunk(emptyLiveTurn(), delta({ content: 'inner' }, { parent_type: 'sub_agent' }));
    expect(t.content).toBe('');
    expect(t.subAgentDeltas).toBe(1);
  });

  it('collects event deltas and snapshots at each event', () => {
    let t = applyChunk(emptyLiveTurn(), delta({ content: 'a' }));
    t = applyChunk(t, delta({ role: 'event', content: 'phase 1' }));
    expect(t.events).toEqual(['phase 1']);
    expect(t.snapshot.content).toBe('a');
  });

  it('rolls back to the last snapshot on redact', () => {
    let t = applyChunk(emptyLiveTurn(), delta({ content: 'good' }));
    t = applyChunk(t, delta({ role: 'event', content: 'attempt' }));
    t = applyChunk(t, delta({ content: ' bad' }));
    t = applyChunk(t, { __redact__: true, message: 'Correcting formatting...' });
    expect(t.content).toBe('good');
    expect(t.redactNotice).toBe('Correcting formatting...');
  });
});

describe('tool calls', () => {
  it('starts a call on a new id and appends argument fragments by id', () => {
    let tools = mergeToolCalls([], [{ id: 'c1', function: { name: 'grep_search', arguments: '{"q"' } }]);
    tools = mergeToolCalls(tools, [{ id: 'c1', function: { arguments: ':1}' } }]);
    expect(tools).toEqual([{ id: 'c1', name: 'grep_search', args: '{"q":1}', result: null }]);
  });

  it('attaches a result by tool_call_id, or to the newest pending call', () => {
    const tools = [
      { id: 'a', name: 'x', args: '', result: null },
      { id: 'b', name: 'y', args: '', result: null },
    ];
    expect(attachResult(tools, { tool_call_id: 'a', content: 'A' })[0]?.result).toBe('A');
    expect(attachResult(tools, { content: 'latest' })[1]?.result).toBe('latest');
  });
});
