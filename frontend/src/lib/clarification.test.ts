import { describe, expect, it } from 'vitest';
import { parseClarification } from './clarification';

describe('parseClarification', () => {
  it('reads the question and options', () => {
    expect(
      parseClarification('c1', '{"question":"Which colour?","options":["Red","Blue"]}'),
    ).toEqual({
      id: 'c1',
      question: 'Which colour?',
      options: ['Red', 'Blue'],
    });
  });

  it('options are optional, and non-string or empty ones are dropped', () => {
    expect(parseClarification('c', '{"question":"Why?"}').options).toEqual([]);
    expect(
      parseClarification('c', '{"question":"q","options":["a",3,"","  ","b"]}').options,
    ).toEqual(['a', 'b']);
    expect(parseClarification('c', '{"question":"q","options":"nope"}').options).toEqual([]);
  });

  it('arguments that do not parse, or hold no question, give the fixed question', () => {
    expect(parseClarification('c', 'not json')).toEqual({
      id: 'c',
      question: 'The assistant needs your input.',
      options: [],
    });
    expect(parseClarification('c', '{"options":["a"]}').question).toBe(
      'The assistant needs your input.',
    );
    expect(parseClarification('c', 'null').question).toBe('The assistant needs your input.');
    expect(parseClarification('c', '').question).toBe('The assistant needs your input.');
  });
});
