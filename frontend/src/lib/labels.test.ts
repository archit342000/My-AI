import { describe, expect, it } from 'vitest';
import { agentLabel, memoryTagLabel, thinkingProfileLabel, titleCase } from './labels';

describe('display labels (F-29)', () => {
  it('maps internal memory tags to readable labels', () => {
    expect(memoryTagLabel('personal_info')).toBe('Personal info');
    expect(memoryTagLabel('preference')).toBe('Preference');
  });

  it('maps agent names and thinking profiles', () => {
    expect(agentLabel('browsing_agent')).toBe('Browsing agent');
    expect(thinkingProfileLabel('precision')).toBe('Precision');
    expect(thinkingProfileLabel('general')).toBe('General');
  });

  it('title-cases unknown names instead of showing the raw identifier', () => {
    expect(agentLabel('deep_scan-agent')).toBe('Deep scan agent');
    expect(titleCase('SOME_KEY')).toBe('Some key');
    expect(titleCase('   ')).toBe('');
  });
});
