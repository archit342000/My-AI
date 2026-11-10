import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  applyDarkClass,
  applyGlass,
  resolveDark,
  resolveGlass,
  supportsBackdropBlur,
} from './theme';

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

describe('resolveGlass', () => {
  it('auto follows what the browser can do; an explicit choice always wins', () => {
    expect(resolveGlass('auto', true)).toBe('frosted');
    expect(resolveGlass('auto', false)).toBe('solid');
    expect(resolveGlass('frosted', false)).toBe('frosted');
    expect(resolveGlass('solid', true)).toBe('solid');
  });
});

describe('supportsBackdropBlur', () => {
  afterEach(() => vi.unstubAllGlobals());

  it('is true when either the standard or the prefixed property is supported', () => {
    vi.stubGlobal('CSS', { supports: (prop: string) => prop === '-webkit-backdrop-filter' });
    expect(supportsBackdropBlur()).toBe(true);
    vi.stubGlobal('CSS', { supports: () => false });
    expect(supportsBackdropBlur()).toBe(false);
  });

  it('is true when only the standard property is supported', () => {
    vi.stubGlobal('CSS', { supports: (prop: string) => prop === 'backdrop-filter' });
    expect(supportsBackdropBlur()).toBe(true);
  });

  it('counts an unknown browser as able to blur', () => {
    vi.stubGlobal('CSS', undefined);
    expect(supportsBackdropBlur()).toBe(true);
  });
});

describe('applyDarkClass and applyGlass', () => {
  afterEach(() => {
    document.documentElement.classList.remove('dark');
    delete document.documentElement.dataset.theme;
    delete document.documentElement.dataset.glass;
  });

  it('sets the dark class and data-theme together', () => {
    applyDarkClass(true);
    expect(document.documentElement.classList.contains('dark')).toBe(true);
    expect(document.documentElement.dataset.theme).toBe('dark');
    applyDarkClass(false);
    expect(document.documentElement.classList.contains('dark')).toBe(false);
    expect(document.documentElement.dataset.theme).toBe('light');
  });

  it('sets data-glass', () => {
    applyGlass('solid');
    expect(document.documentElement.dataset.glass).toBe('solid');
  });
});

describe('public/theme-init.js (data-theme and data-glass before first paint)', () => {
  const source = readFileSync(resolve(__dirname, '../../public/theme-init.js'), 'utf8');

  function run(theme: string | null, glass: string | null, prefersDark: boolean, canBlur: boolean) {
    localStorage.clear();
    if (theme !== null) localStorage.setItem('my_ai_theme_mode', theme);
    if (glass !== null) localStorage.setItem('my_ai_glass_mode', glass);
    vi.stubGlobal('matchMedia', () => ({ matches: prefersDark }));
    vi.stubGlobal('CSS', { supports: () => canBlur });
    new Function(source)();
    return { ...document.documentElement.dataset };
  }

  afterEach(() => {
    vi.unstubAllGlobals();
    localStorage.clear();
    document.documentElement.classList.remove('dark');
    delete document.documentElement.dataset.theme;
    delete document.documentElement.dataset.glass;
  });

  it('data-theme matches resolveDark for every mode and OS setting', () => {
    for (const mode of ['light', 'dark', 'system'] as const) {
      for (const prefersDark of [true, false]) {
        expect(run(mode, null, prefersDark, true).theme).toBe(
          resolveDark(mode, prefersDark) ? 'dark' : 'light',
        );
      }
    }
  });

  it('data-glass matches resolveGlass for every mode and browser', () => {
    for (const mode of ['auto', 'frosted', 'solid'] as const) {
      for (const canBlur of [true, false]) {
        expect(run(null, mode, false, canBlur).glass, `${mode} / blur ${canBlur}`).toBe(
          resolveGlass(mode, canBlur),
        );
      }
    }
    expect(run(null, null, false, false).glass).toBe(resolveGlass('auto', false));
    expect(run(null, 'purple', false, true).glass).toBe(resolveGlass('auto', true));
  });

  it('counts the prefixed property alone as able to blur, as the app does', () => {
    localStorage.clear();
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    vi.stubGlobal('CSS', { supports: (prop: string) => prop === '-webkit-backdrop-filter' });
    new Function(source)();
    expect(document.documentElement.dataset.glass).toBe('frosted');
    expect(supportsBackdropBlur()).toBe(true);
  });

  it('with no CSS.supports it assumes blur works, as the app does', () => {
    localStorage.clear();
    vi.stubGlobal('matchMedia', () => ({ matches: false }));
    vi.stubGlobal('CSS', undefined);
    expect(() => new Function(source)()).not.toThrow();
    expect(document.documentElement.dataset.glass).toBe('frosted');
  });
});
