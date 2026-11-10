// Applies the saved theme before the app loads, so a dark-theme user sees no light flash.
// Same rule as `resolveDark` in src/lib/theme.ts (a unit test keeps them in step); the app's own
// `useThemeSync` keeps running after it mounts and follows later changes.
(function () {
  var mode = 'system';
  var prefersDark = false;
  try {
    mode = window.localStorage.getItem('my_ai_theme_mode') || 'system';
  } catch (e) {
    // storage blocked: follow the system
  }
  try {
    prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
  } catch (e) {
    // no media queries: light
  }
  var dark = mode === 'dark' || mode === 'light' ? mode === 'dark' : prefersDark;
  document.documentElement.classList.toggle('dark', dark);
})();
