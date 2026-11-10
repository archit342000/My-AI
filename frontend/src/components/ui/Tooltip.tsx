import { useEffect, useLayoutEffect, useRef, useState, type CSSProperties, type ReactNode } from 'react';
import { createPortal } from 'react-dom';
import { readVisibleViewport, tooltipPosition } from '../../lib/popover-position';

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
  const bubbleRef = useRef<HTMLDivElement>(null);
  const [anchorRect, setAnchorRect] = useState<DOMRect | null>(null);
  const [pos, setPos] = useState<{ left: number; top: number } | null>(null);

  useEffect(() => () => window.clearTimeout(timer.current), []);

  // Once the bubble is on screen its size is known: put it where it fits inside the visible viewport.
  useLayoutEffect(() => {
    const bubble = bubbleRef.current;
    if (!anchorRect || !bubble) return;
    const size = bubble.getBoundingClientRect();
    setPos(tooltipPosition(anchorRect, size, readVisibleViewport()));
  }, [anchorRect]);

  function show(wait: number) {
    window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => {
      const rect = anchorRef.current?.getBoundingClientRect();
      if (rect) setAnchorRect(rect);
    }, wait);
  }

  function hide() {
    window.clearTimeout(timer.current);
    setAnchorRect(null);
    setPos(null);
  }

  const placement: CSSProperties = pos
    ? { left: pos.left, top: pos.top }
    : { left: 0, top: 0, visibility: 'hidden' };

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
      {anchorRect
        ? createPortal(
            <div
              ref={bubbleRef}
              role="tooltip"
              className="ui-tooltip"
              style={placement} // dynamic-style
            >
              {content}
            </div>,
            document.body,
          )
        : null}
    </span>
  );
}
