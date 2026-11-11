import { renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { GlassMode, ThemeMode } from '../state/ui-store';
import { useThemeSync } from './useThemeSync';

/** A matchMedia stand-in whose OS setting can be flipped, and that counts its listeners. */
function stubSystemTheme(dark: boolean) {
  const listeners = new Set<() => void>();
  const media = {
    matches: dark,
    addEventListener: (_: string, cb: () => void) => listeners.add(cb),
    removeEventListener: (_: string, cb: () => void) => listeners.delete(cb),
  };
  vi.stubGlobal('matchMedia', () => media);
  return {
    listeners,
    set(next: boolean) {
      media.matches = next;
      listeners.forEach((cb) => cb());
    },
  };
}

const root = document.documentElement;

afterEach(() => {
  vi.unstubAllGlobals();
  root.classList.remove('dark');
  delete root.dataset.theme;
  delete root.dataset.glass;
});

describe('useThemeSync', () => {
  it('in system mode follows the OS, also when it changes later', () => {
    const os = stubSystemTheme(true);
    renderHook(() => useThemeSync('system', 'auto'));
    expect(root.dataset.theme).toBe('dark');
    expect(root.classList.contains('dark')).toBe(true);
    os.set(false);
    expect(root.dataset.theme).toBe('light');
    expect(root.classList.contains('dark')).toBe(false);
  });

  it('an explicit theme ignores the OS and listens to nothing', () => {
    const os = stubSystemTheme(true);
    renderHook(() => useThemeSync('light', 'auto'));
    expect(root.dataset.theme).toBe('light');
    expect(os.listeners.size).toBe(0);
  });

  it('applies a new mode when it changes and stops listening on unmount', () => {
    const os = stubSystemTheme(false);
    const { rerender, unmount } = renderHook(
      ({ mode }: { mode: ThemeMode }) => useThemeSync(mode, 'auto'),
      { initialProps: { mode: 'system' as ThemeMode } },
    );
    expect(os.listeners.size).toBe(1);
    rerender({ mode: 'dark' });
    expect(root.dataset.theme).toBe('dark');
    expect(os.listeners.size).toBe(0);
    rerender({ mode: 'system' });
    unmount();
    expect(os.listeners.size).toBe(0);
  });

  it('sets data-glass from the panel mode, and auto from what the browser can do', () => {
    stubSystemTheme(false);
    vi.stubGlobal('CSS', { supports: () => false });
    const { rerender } = renderHook(
      ({ glass }: { glass: GlassMode }) => useThemeSync('light', glass),
      { initialProps: { glass: 'auto' as GlassMode } },
    );
    expect(root.dataset.glass).toBe('solid');
    rerender({ glass: 'frosted' });
    expect(root.dataset.glass).toBe('frosted');
    rerender({ glass: 'solid' });
    expect(root.dataset.glass).toBe('solid');
  });
});
