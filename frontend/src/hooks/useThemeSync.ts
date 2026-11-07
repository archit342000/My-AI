import { useEffect } from 'react';
import { applyDarkClass, resolveDark } from '../lib/theme';
import type { ThemeMode } from '../state/ui-store';

/** Keeps the `dark` class on <html> in sync with the chosen mode (and the OS setting in "system"). */
export function useThemeSync(mode: ThemeMode): void {
  useEffect(() => {
    const media = window.matchMedia('(prefers-color-scheme: dark)');
    const apply = () => applyDarkClass(resolveDark(mode, media.matches));
    apply();
    if (mode !== 'system') return undefined;
    media.addEventListener('change', apply);
    return () => media.removeEventListener('change', apply);
  }, [mode]);
}
