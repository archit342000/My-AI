/**
 * Where a popover or tooltip goes. Pure, so it is unit-tested; `Popover` and `Tooltip` measure the DOM and
 * call these. Coordinates are CSS pixels in the layout viewport (what `position: fixed` uses).
 */

export type PopoverPlacement = 'bottom' | 'right' | 'top';

/** The visible part of the page: the visual viewport when there is one (zoom, on-screen keyboard). */
export interface ViewportRect {
  left: number;
  top: number;
  width: number;
  height: number;
  /** Height of the layout viewport: `bottom` offsets of fixed elements count from its bottom edge. */
  layoutHeight: number;
}

export interface Position {
  /** Distance from the layout viewport top; unset when the panel is anchored by its bottom edge. */
  top?: number;
  /** Distance from the layout viewport bottom: the panel grows upward, so its real height does not matter. */
  bottom?: number;
  left: number;
  width: number;
  maxHeight: number;
}

/** The visible viewport right now: the visual viewport when there is one (zoom, on-screen keyboard), else the window. */
export function readVisibleViewport(win: Window = window): ViewportRect {
  const visual = win.visualViewport;
  return {
    left: visual?.offsetLeft ?? 0,
    top: visual?.offsetTop ?? 0,
    width: visual?.width ?? win.innerWidth,
    height: visual?.height ?? win.innerHeight,
    layoutHeight: win.innerHeight,
  };
}

/** Space kept between a popover and the edge of the visible viewport. */
export const MARGIN = 8;
/** Space between a popover and its anchor when it opens below or beside it, or flips upward. */
export const GAP = 4;
/** Space between a `top` panel and its anchor (the composer, the tools button). */
export const TOP_GAP = 8;
/** Below this much room a `bottom` panel flips upward when there is more room above. */
const MIN_BELOW = 220;
const MAX_UPWARD = 480;
const MAX_TOP = 360;
/** Height assumed for a `right` panel before it has been measured. */
const UNMEASURED_HEIGHT = 120;

/** A zero-size rect at a point, so a context menu opens at the pointer with the same placement rules. */
export function zeroRect(x: number, y: number): DOMRect {
  return {
    x,
    y,
    left: x,
    right: x,
    top: y,
    bottom: y,
    width: 0,
    height: 0,
    toJSON: () => ({}),
  } as DOMRect;
}

/**
 * Places the panel next to the anchor. `bottom` opens below and flips upward when the room is short;
 * `top` sits above; `right` opens beside it. A panel that opens upward is anchored by its bottom edge, so it
 * touches its anchor whatever its real height. Everything stays inside the visible viewport.
 * `panelHeight` is the measured height (when known); it lets a `right` panel shift up to fit.
 */
export function computePosition(
  anchor: DOMRect,
  placement: PopoverPlacement,
  width: number | undefined,
  minWidth: number,
  viewport: ViewportRect,
  panelHeight?: number,
): Position {
  const right = viewport.left + viewport.width - MARGIN;
  const bottomEdge = viewport.top + viewport.height - MARGIN;
  const fit = (w: number) => Math.min(w, viewport.width - 2 * MARGIN);
  if (placement === 'right') {
    const w = fit(width ?? minWidth);
    const spaceRight = right - anchor.right - GAP;
    const left = Math.max(
      viewport.left + MARGIN,
      spaceRight >= w ? anchor.right + GAP : anchor.left - GAP - w,
    );
    const top = Math.max(
      viewport.top + MARGIN,
      Math.min(anchor.top, bottomEdge - (panelHeight ?? UNMEASURED_HEIGHT)),
    );
    return { top, left, width: w, maxHeight: bottomEdge - top };
  }
  const w = fit(width ?? Math.max(anchor.width, minWidth));
  const left = Math.max(viewport.left + MARGIN, Math.min(anchor.left, right - w));
  if (placement === 'top') {
    const maxHeight = Math.min(anchor.top - viewport.top - MARGIN - TOP_GAP, MAX_TOP);
    return { bottom: viewport.layoutHeight - anchor.top + TOP_GAP, left, width: w, maxHeight };
  }
  const below = bottomEdge - anchor.bottom - GAP;
  const above = anchor.top - viewport.top - MARGIN - GAP;
  if (below >= MIN_BELOW || below >= above) {
    return { top: anchor.bottom + GAP, left, width: w, maxHeight: below };
  }
  return {
    bottom: viewport.layoutHeight - anchor.top + GAP,
    left,
    width: w,
    maxHeight: Math.min(above, MAX_UPWARD),
  };
}

/** Where the top-left corner of a tooltip of `size` goes: centred above the anchor, inside the viewport, below it when the top is tight. */
export function tooltipPosition(
  anchor: DOMRect,
  size: { width: number; height: number },
  viewport: ViewportRect,
): { left: number; top: number } {
  const centred = anchor.left + anchor.width / 2 - size.width / 2;
  const left = Math.max(
    viewport.left + MARGIN,
    Math.min(centred, viewport.left + viewport.width - MARGIN - size.width),
  );
  const above = anchor.top - TOP_GAP - size.height;
  const below = anchor.bottom + TOP_GAP;
  const bottomLimit = viewport.top + viewport.height - MARGIN - size.height;
  const top = above >= viewport.top + MARGIN ? above : Math.min(below, bottomLimit);
  return { left, top };
}
