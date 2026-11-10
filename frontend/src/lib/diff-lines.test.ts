import { describe, expect, it } from 'vitest';
import { diffRows, diffSummary } from './diff-lines';

const diff = (added: string[], removed: string[]) => ({
  added_lines: added,
  removed_lines: removed,
  stats: { lines_added: added.length, lines_removed: removed.length },
});

describe('diffRows', () => {
  it('lists the removed lines first, then the added ones, each with its kind', () => {
    expect(diffRows(diff(['new a', 'new b'], ['old a']))).toEqual([
      { kind: 'removed', text: 'old a' },
      { kind: 'added', text: 'new a' },
      { kind: 'added', text: 'new b' },
    ]);
  });
  it('is empty when nothing differs', () => {
    expect(diffRows(diff([], []))).toEqual([]);
  });
});

describe('diffSummary', () => {
  it('says how many lines changed, or that nothing did', () => {
    expect(diffSummary(diff(['a', 'b'], ['c']))).toBe('2 added, 1 removed');
    expect(diffSummary(diff([], []))).toBe('No differing lines');
  });
});
