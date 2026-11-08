import { describe, expect, it } from 'vitest';
import { firstSentencePreview } from './preview-text';

describe('firstSentencePreview', () => {
  it('strips headings and keeps the first sentence', () => {
    expect(firstSentencePreview('# ROLE\nYou are a careful editor. You trim filler.')).toBe('ROLE You are a careful editor.');
  });

  it('removes emphasis, code, links and list markers', () => {
    expect(firstSentencePreview('- **Be** `concise` see [the guide](https://x.test)')).toBe('Be concise see the guide');
  });

  it('returns the whole text when there is no sentence end', () => {
    expect(firstSentencePreview('Summarise notes')).toBe('Summarise notes');
  });

  it('returns an empty string for blank input', () => {
    expect(firstSentencePreview('   \n ')).toBe('');
  });
});
