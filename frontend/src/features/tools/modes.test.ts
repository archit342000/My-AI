import { describe, expect, it } from 'vitest';
import { availableModes, TOOL_MODES } from './modes';

describe('tool modes', () => {
  it('offers Git to the admin only', () => {
    expect(availableModes(true)).toEqual(TOOL_MODES);
    expect(availableModes(false).map((m) => m.key)).not.toContain('gitMode');
    expect(availableModes(false)).toHaveLength(TOOL_MODES.length - 1);
  });

  it('every mode has a short name and a description', () => {
    for (const mode of TOOL_MODES) {
      expect(mode.name.length).toBeGreaterThan(0);
      expect(mode.name.length).toBeLessThanOrEqual(10);
      expect(mode.description.length).toBeGreaterThan(10);
    }
  });
});
