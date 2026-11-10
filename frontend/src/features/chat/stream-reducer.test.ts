import { describe, expect, it } from 'vitest';
import { lastEvent, turnReasoning, turnText, turnTools, type Step } from '../../lib/chat-model';
import { applyChunk, attachResult, emptyLiveTurn, mergeToolCalls, StreamError } from './stream-reducer';

const delta = (d: Record<string, unknown>, extra: Record<string, unknown> = {}) => ({ choices: [{ delta: d }], ...extra });
const tool = (id: string, result: string | null = null, agent: string | null = null): Step => ({
  kind: 'tool',
  id,
  name: 'x',
  args: '',
  result,
  agent,
});

describe('applyChunk', () => {
  it('accumulates content and reasoning into one step each', () => {
    let t = emptyLiveTurn();
    t = applyChunk(t, delta({ content: 'Hel' }));
    t = applyChunk(t, delta({ content: 'lo' }));
    t = applyChunk(t, delta({ reasoning_content: 'think' }));
    expect(turnText(t.steps)).toBe('Hello');
    expect(turnReasoning(t.steps)).toBe('think');
    expect(t.steps.map((s) => s.kind)).toEqual(['text', 'reasoning']);
  });

  it('starts separate steps per round instead of concatenating text', () => {
    let t = emptyLiveTurn();
    t = applyChunk(t, delta({ reasoning_content: 'r1' }));
    t = applyChunk(t, delta({ content: 'First.' }));
    t = applyChunk(t, delta({ tool_calls: [{ id: 'c1', function: { name: 'grep_search', arguments: '{}' } }] }));
    t = applyChunk(t, delta({ tool_result: { tool_call_id: 'c1', content: 'hit' } }));
    t = applyChunk(t, delta({ reasoning_content: 'r2' }));
    t = applyChunk(t, delta({ content: 'Second.' }));
    expect(t.steps.map((s) => s.kind)).toEqual(['reasoning', 'text', 'tool', 'reasoning', 'text']);
    expect(turnText(t.steps)).toBe('First.\n\nSecond.');
    expect(turnTools(t.steps)).toEqual([{ id: 'c1', name: 'grep_search', args: '{}', result: 'hit' }]);
  });

  it('records the model name', () => {
    expect(applyChunk(emptyLiveTurn(), { model: 'gemma' }).model).toBe('gemma');
  });

  it('throws on an error chunk', () => {
    expect(() => applyChunk(emptyLiveTurn(), { error: 'boom' })).toThrow(StreamError);
  });

  it('keeps sub-agent content out of the answer text but in the steps', () => {
    const t = applyChunk(emptyLiveTurn(), delta({ content: 'inner' }, { parent_type: 'sub_agent' }));
    expect(turnText(t.steps)).toBe('');
    expect(t.steps).toEqual([{ kind: 'text', text: 'inner', agent: 'sub_agent' }]);
  });

  it('places sub-agent steps after the running tool and before the next one', () => {
    let t = emptyLiveTurn();
    t = applyChunk(
      t,
      delta({
        tool_calls: [
          { id: 'a', function: { name: 'agent' } },
          { id: 'b', function: { name: 'agent' } },
        ],
      }),
    );
    t = applyChunk(t, delta({ reasoning_content: 'sub thinks' }, { parent_type: 'researcher' }));
    t = applyChunk(t, delta({ reasoning_content: ' more' }, { parent_type: 'researcher' }));
    t = applyChunk(t, delta({ tool_result: { tool_call_id: 'a', content: 'A' } }));
    t = applyChunk(t, delta({ content: 'sub two' }, { parent_type: 'researcher' }));
    expect(t.steps.map((s) => (s.kind === 'tool' ? `tool:${s.id}` : `${s.kind}:${s.agent}`))).toEqual([
      'tool:a',
      'reasoning:researcher',
      'tool:b',
      'text:researcher',
    ]);
    expect(t.steps[1]).toMatchObject({ text: 'sub thinks more' });
  });

  it('collects event deltas as steps and snapshots at each event', () => {
    let t = applyChunk(emptyLiveTurn(), delta({ content: 'a' }));
    t = applyChunk(t, delta({ role: 'event', content: 'phase 1' }));
    expect(lastEvent(t.steps)).toBe('phase 1');
    expect(t.snapshot).toEqual([
      { kind: 'text', text: 'a', agent: null },
      { kind: 'event', text: 'phase 1', agent: null },
    ]);
  });

  it('adds no step for an empty event delta (the saved path drops empty events too)', () => {
    let t = applyChunk(emptyLiveTurn(), delta({ content: 'a' }));
    t = applyChunk(t, delta({ role: 'event', content: '' }));
    expect(t.steps).toEqual([{ kind: 'text', text: 'a', agent: null }]);
    expect(lastEvent(t.steps)).toBeNull();
  });

  it('rolls back to the last snapshot on redact', () => {
    let t = applyChunk(emptyLiveTurn(), delta({ content: 'good' }));
    t = applyChunk(t, delta({ role: 'event', content: 'attempt' }));
    t = applyChunk(t, delta({ content: ' bad' }));
    t = applyChunk(t, { __redact__: true, message: 'Correcting formatting...' });
    expect(turnText(t.steps)).toBe('good');
    expect(t.redactNotice).toBe('Correcting formatting...');
  });
});

describe('tool calls', () => {
  it('starts a call on a new id and appends argument fragments by id', () => {
    let steps = mergeToolCalls([], [{ id: 'c1', function: { name: 'grep_search', arguments: '{"q"' } }]);
    steps = mergeToolCalls(steps, [{ id: 'c1', function: { arguments: ':1}' } }]);
    expect(turnTools(steps)).toEqual([{ id: 'c1', name: 'grep_search', args: '{"q":1}', result: null }]);
  });

  it('continues a call by index when a fragment has no id', () => {
    let steps = mergeToolCalls([], [
      { id: 'a', index: 0, function: { name: 'x', arguments: '{' } },
      { id: 'b', index: 1, function: { name: 'y', arguments: '{' } },
    ]);
    steps = mergeToolCalls(steps, [{ index: 1, function: { arguments: '}' } }]);
    expect(turnTools(steps).map((t) => t.args)).toEqual(['{', '{}']);
  });

  it('does not write a no-id fragment of a new round into a finished call of the previous round', () => {
    let steps = mergeToolCalls([], [{ id: 'a', index: 0, function: { name: 'x', arguments: '{' } }]);
    steps = attachResult(steps, { tool_call_id: 'a', content: 'A' });
    steps = mergeToolCalls(steps, [{ id: 'b', index: 0, function: { name: 'y', arguments: '{' } }]);
    steps = mergeToolCalls(steps, [{ index: 0, function: { arguments: '}' } }]);
    expect(turnTools(steps).map((t) => `${t.id}:${t.args}`)).toEqual(['a:{', 'b:{}']);
  });

  it('attaches a result by tool_call_id, or to the newest pending call', () => {
    const steps = [tool('a'), tool('b')];
    expect(turnTools(attachResult(steps, { tool_call_id: 'a', content: 'A' }))[0]?.result).toBe('A');
    expect(turnTools(attachResult(steps, { content: 'latest' }))[1]?.result).toBe('latest');
  });
});
