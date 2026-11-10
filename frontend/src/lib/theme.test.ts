import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { resolveDark } from './theme';

describe('resolveDark', () => {
  it('follows the OS only in system mode', () => {
    expect(resolveDark('system', true)).toBe(true);
    expect(resolveDark('system', false)).toBe(false);
    expect(resolveDark('dark', false)).toBe(true);
    expect(resolveDark('light', true)).toBe(false);
  });
});

describe('public/theme-init.js (the theme before first paint)', () => {
  const source = readFileSync(resolve(__dirname, '../../public/theme-init.js'), 'utf8');

  function run(stored: string | null, prefersDark: boolean): boolean {
    localStorage.clear();
    if (stored !== null) localStorage.setItem('my_ai_theme_mode', stored);
    vi.stubGlobal('matchMedia', () => ({ matches: prefersDark }));
    document.documentElement.classList.remove('dark');
    new Function(source)();
    return document.documentElement.classList.contains('dark');
  }

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    document.documentElement.classList.remove('dark');
  });

  it('sets the dark class exactly as resolveDark says, for every mode and OS setting', () => {
    for (const mode of ['light', 'dark', 'system'] as const) {
      for (const prefersDark of [true, false]) {
        expect(run(mode, prefersDark), `${mode} / OS dark ${prefersDark}`).toBe(
          resolveDark(mode, prefersDark),
        );
      }
    }
  });

  it('with nothing stored, or something unknown, it follows the system like the app does', () => {
    for (const prefersDark of [true, false]) {
      expect(run(null, prefersDark)).toBe(resolveDark('system', prefersDark));
      expect(run('purple', prefersDark)).toBe(resolveDark('system', prefersDark));
    }
  });

  it('survives blocked storage and a missing media query', () => {
    vi.stubGlobal('localStorage', {
      getItem: () => {
        throw new Error('blocked');
      },
    });
    vi.stubGlobal('matchMedia', undefined);
    document.documentElement.classList.remove('dark');
    expect(() => new Function(source)()).not.toThrow();
    expect(document.documentElement.classList.contains('dark')).toBe(false);
  });
});
