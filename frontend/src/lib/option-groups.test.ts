import { describe, expect, it } from 'vitest';
import { groupOptions } from './option-groups';
import { cx } from './cx';
import { rovingTarget } from './roving';

describe('groupOptions', () => {
  it('lists ungrouped options first and numbers in rendered order', () => {
    const groups = groupOptions([
      { value: 'a', label: 'A', group: 'Hosted' },
      { value: 'b', label: 'B' },
      { value: 'c', label: 'C', group: 'Local' },
      { value: 'd', label: 'D', group: 'Hosted' },
    ]);
    expect(groups.map((g) => g.name)).toEqual([null, 'Hosted', 'Local']);
    const flat = groups.flatMap((g) => g.options).map((o) => [o.value, o.index]);
    expect(flat).toEqual([
      ['b', 0],
      ['a', 1],
      ['d', 2],
      ['c', 3],
    ]);
  });

  it('returns no groups for no options', () => {
    expect(groupOptions([])).toEqual([]);
  });
});

describe('rovingTarget', () => {
  it('wraps at both ends and jumps with Home and End', () => {
    expect(rovingTarget('ArrowRight', 2, 3)).toBe(0);
    expect(rovingTarget('ArrowLeft', 0, 3)).toBe(2);
    expect(rovingTarget('Home', 2, 3)).toBe(0);
    expect(rovingTarget('End', 0, 3)).toBe(2);
    expect(rovingTarget('a', 0, 3)).toBeNull();
    expect(rovingTarget('ArrowDown', 0, 0)).toBeNull();
  });
});

describe('cx', () => {
  it('drops falsy parts', () => {
    expect(cx('a', false, null, undefined, 'b')).toBe('a b');
  });
});
