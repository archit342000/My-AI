import { useEffect, useRef } from 'react';
import { startParticles } from '../../lib/particles';

/** Full-screen particle canvas behind the app (legacy `#ambient-bg` / `#bg-stars`). */
export function AmbientBackground() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return undefined;
    return startParticles({ canvas, isDark: () => document.documentElement.classList.contains('dark') });
  }, []);

  return (
    <div id="ambient-bg">
      <canvas id="bg-stars" ref={canvasRef} />
    </div>
  );
}
