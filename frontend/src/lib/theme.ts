import type { ThemeMode } from '../state/ui-store';

/** Resolves a theme mode to dark/light. `prefersDark` is the OS setting (used only for "system"). */
export function resolveDark(mode: ThemeMode, prefersDark: boolean): boolean {
  if (mode === 'system') return prefersDark;
  return mode === 'dark';
}

/** Applies the resolved theme as the `dark` class on <html>, as the legacy UI does. */
export function applyDarkClass(isDark: boolean): void {
  document.documentElement.classList.toggle('dark', isDark);
}
