import { describe, it, expect } from 'vitest';
import { nextArtifactTitle } from './artifact-names';

describe('nextArtifactTitle', () => {
  it('uses Untitled when nothing is loaded', () => {
    expect(nextArtifactTitle([])).toBe('Untitled');
  });

  it('uses Untitled when no loaded title is exactly Untitled', () => {
    expect(nextArtifactTitle(['notes.md', 'Untitled 2'])).toBe('Untitled');
  });

  it('uses Untitled 2 when only Untitled is taken', () => {
    expect(nextArtifactTitle(['Untitled'])).toBe('Untitled 2');
  });

  it('takes the lowest free number after Untitled 2', () => {
    expect(nextArtifactTitle(['Untitled', 'Untitled 2', 'Untitled 4'])).toBe('Untitled 3');
  });
});
