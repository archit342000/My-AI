import { useEffect, useRef, useState, type ReactNode } from 'react';
import { fadePatches, measureWords, type Box } from '../../lib/sphere-fade';

export interface OnSphereProps {
  children: ReactNode;
  className?: string;
}

/**
 * Words that sit straight on the dot sphere: a status line, a headline, up to three short lines
 * and one row of buttons (rule book 3.3). Draws a soft patch behind each line and each button, and
 * measures again when the size, the text or the typeface changes.
 */
export function OnSphere({ children, className }: OnSphereProps) {
  const ref = useRef<HTMLDivElement>(null);
  const [patches, setPatches] = useState<Box[]>([]);

  useEffect(() => {
    const element = ref.current;
    if (!element) return undefined;
    let cancelled = false;
    const fit = () => {
      if (cancelled) return;
      const next = fadePatches(measureWords(element), element.getBoundingClientRect());
      setPatches((current) => (JSON.stringify(current) === JSON.stringify(next) ? current : next));
    };
    fit();
    const resizes = typeof ResizeObserver === 'undefined' ? null : new ResizeObserver(fit);
    resizes?.observe(element);
    const edits = new MutationObserver(fit);
    edits.observe(element, { childList: true, characterData: true, subtree: true });
    void document.fonts?.ready.then(fit);
    return () => {
      cancelled = true;
      resizes?.disconnect();
      edits.disconnect();
    };
  }, []);

  return (
    <div ref={ref} className={className ? `on-sphere ${className}` : 'on-sphere'}>
      <div className="fade-layer" aria-hidden="true">
        {patches.map((patch) => (
          <i key={`${patch.left}:${patch.top}:${patch.width}:${patch.height}`} style={patch} /> // dynamic-style
        ))}
      </div>
      {children}
    </div>
  );
}
