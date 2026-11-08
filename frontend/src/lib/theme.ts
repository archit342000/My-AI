import hljsDark from 'highlight.js/styles/github-dark.min.css?inline';
import hljsLight from 'highlight.js/styles/github.min.css?inline';
import type { ThemeMode } from '../state/ui-store';

/** Resolves a theme mode to dark/light. `prefersDark` is the OS setting (used only for "system"). */
export function resolveDark(mode: ThemeMode, prefersDark: boolean): boolean {
  if (mode === 'system') return prefersDark;
  return mode === 'dark';
}

/** Applies the resolved theme as the `dark` class on <html>, as the legacy UI does. */
/** Legacy parity: swap the highlight.js theme with the page theme (`#highlight-theme`). */
function applyHighlightTheme(dark: boolean): void {
  let el = document.getElementById('highlight-theme') as HTMLStyleElement | null;
  if (!el) {
    el = document.createElement('style');
    el.id = 'highlight-theme';
    document.head.appendChild(el);
  }
  el.textContent = dark ? hljsDark : hljsLight;
}

export function applyDarkClass(isDark: boolean): void {
  document.documentElement.classList.toggle('dark', isDark);
  applyHighlightTheme(isDark);
}
