import { useEffect, useRef } from 'react';
import { pushBackLayer } from '../lib/back-layer';

/**
 * While `open`, Back on a phone calls `onBack` (which should close the layer) before it moves
 * between pages. With `sticky`, Back does not close the layer: `onBack` should say why not.
 */
export function useBackLayer(open: boolean, onBack: () => void, sticky = false): void {
  const latest = useRef(onBack);
  latest.current = onBack;
  useEffect(() => {
    if (!open) return undefined;
    return pushBackLayer(() => latest.current(), { sticky });
  }, [open, sticky]);
}
