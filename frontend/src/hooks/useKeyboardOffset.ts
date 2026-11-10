import { useEffect, useState } from 'react';
import { computeKeyboardOffset } from '../lib/scroll';

/**
 * Pixels the on-screen keyboard covers at the bottom of the layout viewport (touch devices only).
 * The composer uses this as `translateY(-offset)`, as the legacy `initScrollManager` did; it is also published as
 * `--keyboard-offset` on `<html>`.
 */
export function useKeyboardOffset(enabled: boolean): number {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const vv = window.visualViewport;
    const root = document.documentElement;
    if (!enabled || !vv) {
      setOffset(0);
      return undefined;
    }
    const sync = () => {
      const next = computeKeyboardOffset(window.innerHeight, vv.height, vv.offsetTop);
      setOffset(next);
      // The transcript pads its bottom by this, so its content ends above the raised composer.
      root.style.setProperty('--keyboard-offset', `${next}px`);
    };
    sync();
    vv.addEventListener('resize', sync);
    vv.addEventListener('scroll', sync);
    return () => {
      vv.removeEventListener('resize', sync);
      vv.removeEventListener('scroll', sync);
      root.style.removeProperty('--keyboard-offset');
    };
  }, [enabled]);

  return offset;
}
