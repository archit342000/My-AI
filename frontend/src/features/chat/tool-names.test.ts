import { describe, expect, it } from 'vitest';
import { friendlyToolName } from './tool-names';

describe('friendlyToolName', () => {
  it('uses the curated label when one exists', () => {
    expect(friendlyToolName('run_shell_command')).toBe('Terminal');
    expect(friendlyToolName('grep_search')).toBe('Search Code');
  });

  it('title-cases unknown tool names', () => {
    expect(friendlyToolName('summarise_pdf_pages')).toBe('Summarise Pdf Pages');
    expect(friendlyToolName('lookup  thing')).toBe('Lookup Thing');
  });
});
