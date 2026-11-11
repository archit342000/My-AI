import hljsDark from 'highlight.js/styles/github-dark.min.css?inline';
import hljsLight from 'highlight.js/styles/github.min.css?inline';
import type { GlassMode, ThemeMode } from '../state/ui-store';

/** Resolves a theme mode to dark/light. `prefersDark` is the OS setting (used only for "system"). */
export function resolveDark(mode: ThemeMode, prefersDark: boolean): boolean {
  if (mode === 'system') return prefersDark;
  return mode === 'dark';
}

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

/**
 * Applies the resolved theme to <html>: the `dark` class (legacy selectors) and `data-theme`
 * (the shared values in tokens.css). Always set explicitly, so "system" does not rely on the
 * media-query fallback in tokens.css.
 */
export function applyDarkClass(isDark: boolean): void {
  document.documentElement.classList.toggle('dark', isDark);
  document.documentElement.dataset.theme = isDark ? 'dark' : 'light';
  applyHighlightTheme(isDark);
}

export type ResolvedGlass = 'frosted' | 'solid';

/** Resolves the panel mode. "auto" is frosted unless the browser cannot blur what is behind a panel. */
export function resolveGlass(mode: GlassMode, supportsBlur: boolean): ResolvedGlass {
  if (mode === 'auto') return supportsBlur ? 'frosted' : 'solid';
  return mode;
}

/** True when the browser can blur behind an element. Unknown (no CSS.supports) counts as yes. */
export function supportsBackdropBlur(): boolean {
  if (typeof CSS === 'undefined' || typeof CSS.supports !== 'function') return true;
  return (
    CSS.supports('backdrop-filter', 'blur(1px)') ||
    CSS.supports('-webkit-backdrop-filter', 'blur(1px)')
  );
}

/** Applies the resolved panel mode as `data-glass` on <html> (read by tokens.css and bridge.css). */
export function applyGlass(glass: ResolvedGlass): void {
  document.documentElement.dataset.glass = glass;
}
