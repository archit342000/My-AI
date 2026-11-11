// Applies the saved theme and panel mode before the app loads, so a dark-theme user sees no light
// flash and panels never start in the wrong mode. Same rules as `resolveDark`, `resolveGlass` and
// `supportsBackdropBlur` in src/lib/theme.ts (a unit test keeps them in step); the app's own
// `useThemeSync` keeps running after it mounts and follows later changes.
(function () {
  var root = document.documentElement;
  var mode = 'system';
  var glass = 'auto';
  var prefersDark = false;
  var canBlur = true;
  try {
    mode = window.localStorage.getItem('my_ai_theme_mode') || 'system';
    glass = window.localStorage.getItem('my_ai_glass_mode') || 'auto';
  } catch (e) {
    // storage blocked: follow the system
  }
  try {
    prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch (e) {
    // no media queries: light
  }
  try {
    canBlur =
      window.CSS.supports('backdrop-filter', 'blur(1px)') ||
      window.CSS.supports('-webkit-backdrop-filter', 'blur(1px)');
  } catch (e) {
    // cannot tell: assume it can
  }
  var dark = mode === 'dark' || mode === 'light' ? mode === 'dark' : prefersDark;
  root.classList.toggle('dark', dark);
  root.setAttribute('data-theme', dark ? 'dark' : 'light');
  var solid = glass === 'solid' || (glass !== 'frosted' && !canBlur);
  root.setAttribute('data-glass', solid ? 'solid' : 'frosted');
})();
