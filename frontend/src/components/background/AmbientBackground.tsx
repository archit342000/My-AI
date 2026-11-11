import { useEffect, useRef, useState } from 'react';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { startParticles } from '../../lib/particles';

/** Full-screen particle canvas behind the app (legacy `#ambient-bg` / `#bg-stars`). */
export function AmbientBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const reduced = useMediaQuery('(prefers-reduced-motion: reduce)');
  // With less motion the canvas is one still frame, so a theme change has to redraw it.
  const [themeTick, setThemeTick] = useState(0);

  useEffect(() => {
    if (!reduced) return undefined;
    const root = document.documentElement;
    let wasDark = root.classList.contains('dark');
    // Other classes come and go on <html> (for example `is-ios`): redraw only when the theme flips.
    const watch = new MutationObserver(() => {
      const dark = root.classList.contains('dark');
      if (dark === wasDark) return;
      wasDark = dark;
      setThemeTick((n) => n + 1);
    });
    watch.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => watch.disconnect();
  }, [reduced]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    return startParticles({
      canvas,
      isDark: () => document.documentElement.classList.contains('dark'),
      reduceMotion: () => reduced,
    });
    // themeTick is not read: it only restarts the still frame after a theme flip.
  }, [reduced, themeTick]);

  return (
    <div id="ambient-bg">
      <canvas id="bg-stars" ref={canvasRef} />
    </div>
  );
}
