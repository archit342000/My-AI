import { useEffect, useRef, useState, type ReactNode } from 'react';
import { createPortal } from 'react-dom';

export interface TooltipProps {
  content: ReactNode;
  children: ReactNode;
  /** Hover delay in ms. Keyboard focus shows the tooltip immediately. */
  delay?: number;
}

/**
 * Hover and focus hint rendered in a portal above the child. Hidden on mouse leave, blur or
 * Escape. Not a substitute for an accessible name: icon-only buttons still need `aria-label`.
 */
export function Tooltip({ content, children, delay = 350 }: TooltipProps) {
  const anchorRef = useRef<HTMLSpanElement>(null);
  const timer = useRef<number | undefined>(undefined);
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  function show(wait: number) {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const rect = anchorRef.current?.getBoundingClientRect();
      if (rect) setPos({ x: rect.left + rect.width / 2, y: rect.top });
    }, wait);
  }

  function hide() {
    window.clearTimeout(timer.current);
    setPos(null);
  }

  return (
    <span
      ref={anchorRef}
      className="ui-tooltip-anchor"
      onMouseEnter={() => show(delay)}
      onMouseLeave={hide}
      onFocus={() => show(0)}
      onBlur={hide}
      onKeyDown={(event) => {
        if (event.key === 'Escape') hide();
      }}
    >
      {children}
      {pos
        ? createPortal(
            <div role="tooltip" className="ui-tooltip" style={{ left: pos.x, top: pos.y - 8, transform: 'translate(-50%, -100%)' }} /* dynamic-style */>
              {content}
            </div>,
            document.body,
          )
        : null}
    </span>
  );
}
