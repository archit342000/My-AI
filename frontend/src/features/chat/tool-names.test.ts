import { describe, expect, it } from 'vitest';
import { friendlyToolName } from './tool-names';

describe('friendlyToolName', () => {
  it('uses the curated label when one exists', () => {
    expect(friendlyToolName('run_shell_command')).toBe('Terminal');
    expect(friendlyToolName('grep_search')).toBe('Search code');
    expect(friendlyToolName('google_web_search')).toBe('Google search');
  });

  it('writes unknown tool names in words, with a capital only on the first word and on proper names', () => {
    expect(friendlyToolName('summarise_pdf_pages')).toBe('Summarise PDF pages');
    expect(friendlyToolName('lookup  thing')).toBe('Lookup thing');
  });
});
