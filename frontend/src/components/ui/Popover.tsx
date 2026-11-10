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
import {
  computePosition,
  readVisibleViewport,
  zeroRect,
  type PopoverPlacement,
  type Position,
} from '../../lib/popover-position';
import { pushPopover, type PopoverCloseReason } from './popover-stack';

export type { PopoverPlacement };

export interface PopoverProps {
  open: boolean;
  anchorRef: RefObject<HTMLElement | null>;
  /** Element to place the panel against when it differs from the anchor (the anchor still decides what counts as an outside press). */
  positionRef?: RefObject<HTMLElement | null>;
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

function samePosition(a: Position | null, b: Position): boolean {
  return (
    a !== null &&
    a.top === b.top &&
    a.bottom === b.bottom &&
    a.left === b.left &&
    a.width === b.width &&
    a.maxHeight === b.maxHeight
  );
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
  positionRef,
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
  const panelRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef(onClose);
  useEffect(() => {
    closeRef.current = onClose;
  });

  const pointX = point?.x;
  const pointY = point?.y;

  useLayoutEffect(() => {
    if (!open) return;
    const update = () => {
      const rect =
        pointX !== undefined && pointY !== undefined
          ? zeroRect(pointX, pointY)
          : (positionRef ?? anchorRef).current?.getBoundingClientRect();
      if (!rect) return;
      const next = computePosition(
        rect,
        placement,
        width,
        minWidth,
        readVisibleViewport(),
        panelRef.current?.offsetHeight,
      );
      setPos((current) => (samePosition(current, next) ? current : next));
    };
    update();
    window.addEventListener('resize', update);
    window.addEventListener('scroll', update, true);
    const visual = window.visualViewport;
    visual?.addEventListener('resize', update);
    visual?.addEventListener('scroll', update);
    // The panel's real height decides where a `right` panel must shift to; it changes as content loads.
    const observer =
      typeof ResizeObserver === 'undefined' || !panelRef.current
        ? null
        : new ResizeObserver(update);
    if (observer && panelRef.current) observer.observe(panelRef.current);
    return () => {
      window.removeEventListener('resize', update);
      window.removeEventListener('scroll', update, true);
      visual?.removeEventListener('resize', update);
      visual?.removeEventListener('scroll', update);
      observer?.disconnect();
    };
  }, [open, anchorRef, positionRef, placement, width, minWidth, pointX, pointY]);

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
      ref={panelRef}
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
