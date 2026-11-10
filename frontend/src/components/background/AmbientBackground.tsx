import { useEffect, useRef } from 'react';
import { useMediaQuery } from '../../hooks/useMediaQuery';
import { startParticles, type SphereHandle } from '../../lib/particles';
import { subscribeSphere } from '../../lib/sphere-signal';

/** The dot colours and the star colour, as the shared values define them for the current theme. */
function readPalette(): { dots: string[]; star: string } {
  const style = getComputedStyle(document.documentElement);
  const value = (name: string) => style.getPropertyValue(name).trim();
  return {
    dots: [1, 2, 3, 4, 5].map((n) => value(`--dot-${n}`)),
    star: value('--fg'),
  };
}

/** The background of every screen: night stars and the dot sphere. Strength is set in CSS by `data-dim`. */
export function AmbientBackground() {
  const sphereRef = useRef<HTMLCanvasElement>(null);
  const starsRef = useRef<HTMLCanvasElement>(null);
  const reduced = useMediaQuery('(prefers-reduced-motion: reduce)');

  useEffect(() => {
    const canvas = sphereRef.current;
    if (!canvas) return undefined;
    const root = document.documentElement;
    const sphere: SphereHandle = startParticles({
      canvas,
      starCanvas: starsRef.current,
      isDark: () => root.classList.contains('dark'),
      palette: readPalette,
      reduceMotion: () => reduced,
    });
    const unsubscribe = subscribeSphere((signal) => {
      if (signal.type === 'ripple') sphere.ripple(signal.strength);
      else sphere.setBusy(signal.busy);
    });
    // The colours belong to the theme: read them again when it flips. Other classes come and go
    // on <html> (for example `is-ios`) and change nothing here.
    let wasDark = root.classList.contains('dark');
    const watch = new MutationObserver(() => {
      const dark = root.classList.contains('dark');
      if (dark === wasDark) return;
      wasDark = dark;
      sphere.refresh();
    });
    watch.observe(root, { attributes: true, attributeFilter: ['class'] });
    return () => {
      watch.disconnect();
      unsubscribe();
      sphere.stop();
    };
  }, [reduced]);

  return (
    <div id="ambient-bg" aria-hidden="true">
      <canvas id="bg-night" ref={starsRef} />
      <canvas id="bg-stars" ref={sphereRef} />
    </div>
  );
}
