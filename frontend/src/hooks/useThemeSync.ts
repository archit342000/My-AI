import { useEffect } from 'react';
import {
  applyDarkClass,
  applyGlass,
  resolveDark,
  resolveGlass,
  supportsBackdropBlur,
} from '../lib/theme';
import type { GlassMode, ThemeMode } from '../state/ui-store';

/**
 * Keeps <html> in sync with the chosen theme (and the OS setting in "system") and panel mode:
 * the `dark` class, `data-theme` and `data-glass`.
 */
export function useThemeSync(mode: ThemeMode, glassMode: GlassMode): void {
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => applyDarkClass(resolveDark(mode, media.matches));
    apply();
    if (mode !== 'system') return undefined;
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, [mode]);

  useEffect(() => {
    applyGlass(resolveGlass(glassMode, supportsBackdropBlur()));
  }, [glassMode]);
}
