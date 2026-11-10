import { describe, expect, it } from 'vitest';
import { enableThinkingFor } from './thinking';

describe('enableThinkingFor', () => {
  it('turns thinking off only for the none profile', () => {
    expect(enableThinkingFor('none')).toBe(false);
    expect(enableThinkingFor('general')).toBe(true);
    expect(enableThinkingFor('precision')).toBe(true);
  });

  it('keeps thinking on for an unknown profile', () => {
    expect(enableThinkingFor('something-new')).toBe(true);
  });
});
