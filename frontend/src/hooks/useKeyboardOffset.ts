import { useEffect, useState } from 'react';
import { computeKeyboardOffset } from '../lib/scroll';

/**
 * Pixels the on-screen keyboard covers at the bottom of the layout viewport (touch devices only).
 * The composer uses this as `translateY(-offset)`, as the legacy `initScrollManager` did.
 */
export function useKeyboardOffset(enabled: boolean): number {
  const [offset, setOffset] = useState(0);

  useEffect(() => {
    const vv = window.visualViewport;
    if (!enabled || !vv) {
      setOffset(0);
      return undefined;
    }
    const sync = () => setOffset(computeKeyboardOffset(window.innerHeight, vv.height));
    sync();
    vv.addEventListener('resize', sync);
    vv.addEventListener('scroll', sync);
    return () => {
      vv.removeEventListener('resize', sync);
      vv.removeEventListener('scroll', sync);
    };
  }, [enabled]);

  return offset;
}
