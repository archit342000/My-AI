import { beforeEach, describe, expect, it } from 'vitest';
import { thoughtKey, useThoughtStore } from './thought-store';

describe('thought store', () => {
  beforeEach(() => useThoughtStore.setState({ expanded: {} }));

  it('toggling a key flips it', () => {
    const key = thoughtKey('c1', 2);
    useThoughtStore.getState().toggle(key);
    expect(useThoughtStore.getState().expanded[key]).toBe(true);
    useThoughtStore.getState().toggle(key);
    expect(useThoughtStore.getState().expanded[key]).toBeUndefined();
  });

  it("clearChat removes only that chat's keys", () => {
    const { toggle } = useThoughtStore.getState();
    toggle(thoughtKey('c1', 1));
    toggle(thoughtKey('c1', 2));
    toggle(thoughtKey('c10', 1));
    useThoughtStore.getState().clearChat('c1');
    expect(Object.keys(useThoughtStore.getState().expanded)).toEqual(['c10:1']);
  });
});
