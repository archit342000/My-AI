import { describe, expect, it } from 'vitest';
import {
  computePosition,
  readVisibleViewport,
  tooltipPosition,
  zeroRect,
  type ViewportRect,
} from './popover-position';

const rect = (left: number, top: number, width: number, height: number) =>
  ({ left, top, width, height, right: left + width, bottom: top + height }) as DOMRect;
const vp = (over: Partial<ViewportRect> = {}): ViewportRect => ({
  left: 0,
  top: 0,
  width: 1000,
  height: 800,
  layoutHeight: 800,
  ...over,
});

describe('computePosition', () => {
  it('opens a bottom panel below its anchor when there is room', () => {
    const p = computePosition(rect(100, 100, 200, 30), 'bottom', undefined, 160, vp());
    expect(p).toMatchObject({ top: 134, left: 100, width: 200 });
    expect(p.bottom).toBeUndefined();
    expect(p.maxHeight).toBe(800 - 8 - 130 - 4);
  });

  it('flips upward without room below, anchored by its bottom edge (4px gap, real height does not matter)', () => {
    const anchor = rect(100, 740, 200, 30);
    const p = computePosition(anchor, 'bottom', undefined, 160, vp());
    expect(p.top).toBeUndefined();
    expect(p.bottom).toBe(800 - 740 + 4);
    expect(p.maxHeight).toBe(480); // capped; the room above is 728
  });

  it('keeps a bottom panel below when below is the larger side even if short', () => {
    const p = computePosition(
      rect(0, 300, 100, 30),
      'bottom',
      undefined,
      160,
      vp({ height: 600, layoutHeight: 600 }),
    );
    expect(p.top).toBe(334);
  });

  it('a top panel sits 8px above its anchor', () => {
    const p = computePosition(
      rect(50, 827, 40, 40),
      'top',
      320,
      160,
      vp({ height: 900, layoutHeight: 900 }),
    );
    expect(p).toMatchObject({ bottom: 900 - 827 + 8, left: 50, width: 320 });
    expect(p.top).toBeUndefined();
    expect(p.maxHeight).toBe(360);
  });

  it('a right panel opens beside the anchor and flips left when the right is tight', () => {
    expect(computePosition(rect(100, 100, 100, 30), 'right', 200, 160, vp()).left).toBe(204);
    expect(computePosition(rect(800, 100, 190, 30), 'right', 200, 160, vp()).left).toBe(596);
  });

  it('shifts a right panel up to fit its measured height near the bottom', () => {
    const p = computePosition(rect(100, 760, 100, 30), 'right', 200, 160, vp(), 300);
    expect(p.top).toBe(800 - 8 - 300);
    expect(p.maxHeight).toBe(300);
  });

  it('a point near the bottom opens upward from the point', () => {
    const p = computePosition(zeroRect(500, 780), 'bottom', 180, 160, vp());
    expect(p.top).toBeUndefined();
    expect(p.bottom).toBe(800 - 780 + 4);
  });

  it('respects an offset visual viewport and its layout height', () => {
    const view = vp({ left: 20, top: 100, width: 400, height: 500, layoutHeight: 900 });
    const p = computePosition(rect(0, 540, 100, 30), 'bottom', 150, 160, view);
    expect(p.left).toBe(28); // inside the visible area, 8px from its edge
    expect(p.bottom).toBe(900 - 540 + 4);
  });

  it('never makes a panel wider than the visible width minus the margins', () => {
    const p = computePosition(rect(0, 100, 50, 30), 'bottom', 600, 160, vp({ width: 390 }));
    expect(p.width).toBe(374);
    expect(p.left).toBe(8);
  });
});

describe('tooltipPosition', () => {
  const size = { width: 100, height: 30 };
  it('centres above the anchor', () => {
    expect(tooltipPosition(rect(200, 200, 40, 20), size, vp())).toEqual({ left: 170, top: 162 });
  });
  it('is clamped at both edges', () => {
    expect(tooltipPosition(rect(0, 200, 20, 20), size, vp()).left).toBe(8);
    expect(tooltipPosition(rect(990, 200, 10, 20), size, vp()).left).toBe(1000 - 8 - 100);
  });
  it('goes below the anchor when there is no room above', () => {
    expect(tooltipPosition(rect(200, 10, 40, 20), size, vp()).top).toBe(38);
  });
  it('stays inside the bottom edge when it has to go below an anchor near it', () => {
    const tall = { width: 100, height: 900 };
    expect(
      tooltipPosition(rect(200, 780, 40, 20), tall, vp({ height: 1000, layoutHeight: 1000 })).top,
    ).toBe(92);
    expect(
      tooltipPosition(rect(200, 5, 40, 20), size, vp({ height: 40, layoutHeight: 40 })).top,
    ).toBe(2);
  });
});

describe('readVisibleViewport', () => {
  it('uses the visual viewport when there is one, else the window', () => {
    const win = { innerWidth: 1000, innerHeight: 800, visualViewport: null } as unknown as Window;
    expect(readVisibleViewport(win)).toEqual({
      left: 0,
      top: 0,
      width: 1000,
      height: 800,
      layoutHeight: 800,
    });
    const zoomed = {
      innerWidth: 1000,
      innerHeight: 800,
      visualViewport: { offsetLeft: 5, offsetTop: 7, width: 400, height: 300 },
    } as unknown as Window;
    expect(readVisibleViewport(zoomed)).toEqual({
      left: 5,
      top: 7,
      width: 400,
      height: 300,
      layoutHeight: 800,
    });
  });
});
