import { useEffect } from 'react';

/**
 * Says how strongly the dot sphere shows behind this screen: "open" (home, sign-in, a dead end:
 * full strength) or "read" (everything else: dimmed, the default). Published as `data-dim` on <html>.
 */
export function useSphereDim(dim: 'open' | 'read'): void {
  useEffect(() => {
    const root = document.documentElement;
    root.dataset.dim = dim;
    return () => {
      root.dataset.dim = 'read';
    };
  }, [dim]);
}
