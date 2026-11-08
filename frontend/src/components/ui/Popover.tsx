import {
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type CSSProperties,
  type ReactNode,
  type RefObject,
} from 'react';
import { createPortal } from 'react-dom';
import { cx } from '../../lib/cx';
import { pushPopover, type PopoverCloseReason } from './popover-stack';

export type PopoverPlacement = 'bottom' | 'right' | 'top';

export interface PopoverProps {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
  /** Anchor at a viewport point instead of an element (context menus). Takes precedence over `anchorRef`. */
  point?: { x: number; y: number };
  /** Called on Escape (top-most popover only) or a pointer down outside every popover and the anchor. */
  onClose: (reason: PopoverCloseReason) => void;
  children: ReactNode;
  placement?: PopoverPlacement;
  /** Fixed width in px. Defaults to the anchor width for `bottom`. */
  width?: number;
  minWidth?: number;
  role?: 'menu' | 'listbox' | 'dialog';
  label?: string;
  id?: string;
  className?: string;
}

interface Position {
  /** Distance from the viewport top; unset for `top` placement, which anchors by `bottom`. */
  top?: number;
  /** Distance from the viewport bottom; used by `top` placement so the panel grows upward. */
  bottom?: number;
  left: number;
  width: number;
  maxHeight: number;
}

const MARGIN = 8;
const GAP = 4;

/** A zero-size rect at a point, so a context menu opens at the pointer with the same placement rules. */
function zeroRect(x: number, y: number): DOMRect {
  return { x, y, left: x, right: x, top: y, bottom: y, width: 0, height: 0, toJSON: () => ({}) } as DOMRect;
}
/** Space between a `top` panel and its anchor (the composer). */
const TOP_GAP = 8;

/** Places the panel next to the anchor: `bottom` and `right` flip when the viewport is short, `top` sits above. */
function computePosition(
  anchor: DOMRect,
  placement: PopoverPlacement,
  width: number | undefined,
  minWidth: number,
  viewport: { width: number; height: number },
): Position {
  if (placement === 'right') {
    const w = width ?? minWidth;
    const spaceRight = viewport.width - anchor.right - MARGIN - GAP;
    const left =
      spaceRight >= w ? anchor.right + GAP : Math.max(MARGIN, anchor.left - GAP - w);
    const top = Math.max(MARGIN, Math.min(anchor.top, viewport.height - MARGIN - 120));
    return { top, left, width: w, maxHeight: viewport.height - top - MARGIN };
  }
  const w = width ?? Math.max(anchor.width, minWidth);
  const left = Math.max(MARGIN, Math.min(anchor.left, viewport.width - w - MARGIN));
  if (placement === 'top') {
    // Above the anchor (composer autocomplete), never taller than the space available. Anchored by
    // the bottom edge so a short list still sits directly on top of the anchor.
    const maxHeight = Math.min(anchor.top - MARGIN - TOP_GAP, 360);
    return { bottom: viewport.height - anchor.top + TOP_GAP, left, width: w, maxHeight };
  }
  const below = viewport.height - anchor.bottom - MARGIN - GAP;
  const above = anchor.top - MARGIN - GAP;
  if (below >= 220 || below >= above) {
    return { top: anchor.bottom + GAP, left, width: w, maxHeight: below };
  }
  const maxHeight = Math.min(above, 480);
  return { top: anchor.top - GAP - maxHeight, left, width: w, maxHeight };
}

/**
 * Portalled surface for menus, listboxes and autocomplete. Opaque (`--surface-elevated`) so it
 * never picks up the blur behind it, positioned from the anchor, closed by Escape and outside
 * pointer down. It is rendered to `document.body`, so no ancestor's `backdrop-filter` or
 * `overflow` clips it. Panels carry `data-popover`, so pointer events inside any popover count as
 * inside for every popover (nested submenus stay open).
 */
export function Popover({
  open,
  anchorRef,
  point,
  onClose,
  children,
  placement = 'bottom',
  width,
  minWidth = 160,
  role,
  label,
  id,
  className,
}: PopoverProps) {
  const [pos, setPos] = useState<Position | null>(null);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  });

  const pointX = point?.x;
  const pointY = point?.y;
  const hasPoint = pointX !== undefined && pointY !== undefined;

  useLayoutEffect(() => {
    if (!open) return;
    const update = () => {
      const rect = hasPoint
        ? zeroRect(pointX as number, pointY as number)
        : anchorRef.current?.getBoundingClientRect();
      if (!rect) return;
      setPos(
        computePosition(rect, placement, width, minWidth, {
          width: window.innerWidth,
          height: window.innerHeight,
        }),
      );
    };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
    };
  }, [open, anchorRef, placement, width, minWidth, hasPoint, pointX, pointY]);

  useEffect(() => {
    if (!open) return;
    const release = pushPopover((reason) => closeRef.current(reason));
    function onPointerDown(event: PointerEvent) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest('[data-popover]') || anchorRef.current?.contains(target)) return;
      closeRef.current('outside');
    }
    document.addEventListener('pointerdown', onPointerDown);
    return () => {
      release();
      document.removeEventListener('pointerdown', onPointerDown);
    };
  }, [open, anchorRef]);

  if (!open) return null;

  const placementStyle: CSSProperties = pos
    ? {
        top: pos.top,
        bottom: pos.bottom,
        left: pos.left,
        width: pos.width,
        maxHeight: pos.maxHeight,
      }
    : { top: 0, left: 0, visibility: 'hidden' };

  return createPortal(
    <div
      data-popover=""
      id={id}
      role={role}
      aria-label={label}
      className={cx('ui-popover', className)}
      style={placementStyle} // dynamic-style
    >
      {children}
    </div>,
    document.body,
  );
}
