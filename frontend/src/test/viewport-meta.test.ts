import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe('viewport meta', () => {
  const html = readFileSync(resolve(__dirname, '../../index.html'), 'utf8');
  const content = /<meta\s+name="viewport"\s+content="([^"]*)"/.exec(html)?.[1] ?? '';

  it('matches the legacy page: resizes with the keyboard, no zoom, safe-area aware', () => {
    for (const part of [
      'width=device-width',
      'initial-scale=1.0',
      'maximum-scale=1.0',
      'user-scalable=no',
      'viewport-fit=cover',
      'interactive-widget=resizes-content',
    ]) {
      expect(content).toContain(part);
    }
  });
});
