import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createParticles,
  createStars,
  GOLDEN_ANGLE,
  particleAlpha,
  particleCount,
  particleRadius,
  rotatePoint,
  SIZE_FACTOR,
  sphereStretch,
  startParticles,
} from './particles';

describe('particles', () => {
  it('uses 600 dots on a computer and 250 on a phone or touch device', () => {
    expect(particleCount(true)).toBe(250);
    expect(particleCount(false)).toBe(600);
  });

  it('sizes the sphere per viewport and draws it at 75%', () => {
    expect(particleRadius(390, 844)).toBeCloseTo(390 * 0.42);
    expect(particleRadius(1440, 900)).toBeCloseTo(Math.max(300, 900 * 0.28));
    expect(particleRadius(700, 500)).toBe(300);
    expect(SIZE_FACTOR).toBe(0.75);
  });

  it('is a true ball on anything wider than a phone, however wide the window', () => {
    expect(sphereStretch(1440, 900)).toEqual({ x: 1, y: 1 });
    expect(sphereStretch(2560, 900)).toEqual({ x: 1, y: 1 });
    expect(sphereStretch(820, 1180)).toEqual({ x: 1, y: 1 });
  });

  it('on a phone grows slightly along the longer side, never past 1.3', () => {
    const tall = sphereStretch(390, 844);
    expect(tall.x).toBe(1);
    expect(tall.y).toBeCloseTo(Math.min(1.3, 1 + (844 / 390 - 1) * 0.3));
    expect(sphereStretch(320, 2000).y).toBe(1.3);
  });

  it('places dots on the unit sphere by the golden angle, with bounded size, distance and colour', () => {
    const ps = createParticles(50, () => 0.5);
    expect(ps).toHaveLength(50);
    ps.forEach((p, i) => {
      expect(Math.hypot(p.ux, p.uy, p.uz)).toBeCloseTo(1, 5);
      expect(p.uz).toBeCloseTo(1 - (2 * (i + 0.5)) / 50, 5);
      expect(Math.atan2(p.uy, p.ux)).toBeCloseTo(
        Math.atan2(Math.sin(i * GOLDEN_ANGLE), Math.cos(i * GOLDEN_ANGLE)),
        5,
      );
      expect(p.size).toBeGreaterThanOrEqual(1.5);
      expect(p.size).toBeLessThanOrEqual(4);
      expect(p.distRatio).toBeCloseTo(1, 5);
    });
    for (const p of createParticles(200)) {
      expect(p.colorIndex).toBeGreaterThanOrEqual(0);
      expect(p.colorIndex).toBeLessThanOrEqual(4);
      expect(p.distRatio).toBeGreaterThanOrEqual(0.55);
      expect(p.distRatio).toBeLessThanOrEqual(1.45);
    }
    expect(createParticles(5, () => 0.999999)[0]?.colorIndex).toBe(4);
  });

  it('keeps the rotation length-preserving', () => {
    const p = { x: 3, y: 4, z: 0 };
    const r = rotatePoint(p, 0.7, 1.3);
    expect(Math.hypot(r.x, r.y, r.z)).toBeCloseTo(5, 5);
  });

  it('clamps alpha to the theme range', () => {
    expect(particleAlpha(1e6, 300, false)).toBeLessThanOrEqual(0.92);
    expect(particleAlpha(1e6, 300, true)).toBeLessThanOrEqual(0.98);
    expect(particleAlpha(-1e6, 300, false)).toBeGreaterThanOrEqual(0.1);
  });

  it('draws the same still stars every time, inside the screen, more on a bigger one', () => {
    const a = createStars(1440, 900);
    expect(createStars(1440, 900)).toEqual(a);
    expect(a.length).toBe(Math.round((1440 * 900) / 6500));
    expect(createStars(390, 844).length).toBeLessThan(a.length);
    for (const star of a) {
      expect(star.x).toBeGreaterThanOrEqual(0);
      expect(star.x).toBeLessThanOrEqual(1440);
      expect(star.y).toBeLessThanOrEqual(900);
    }
  });
});

describe('startParticles and reduced motion', () => {
  const stops: Array<() => void> = [];
  const originalWidth = window.innerWidth;

  afterEach(() => {
    stops.splice(0).forEach((stop) => stop());
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalWidth });
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
  });

  function fakeContext() {
    return {
      setTransform: vi.fn(),
      clearRect: vi.fn(),
      beginPath: vi.fn(),
      arc: vi.fn(),
      fill: vi.fn(),
      globalAlpha: 1,
      fillStyle: '',
    };
  }

  /** Starts the canvas with a hand-run frame queue and runs its first frame. */
  function start(reduce: boolean) {
    const queue: FrameRequestCallback[] = [];
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => queue.push(cb));
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    const ctx = fakeContext();
    const canvas = document.createElement('canvas');
    vi.spyOn(canvas, 'getContext').mockReturnValue(ctx as unknown as CanvasRenderingContext2D);
    const sphere = startParticles({
      canvas,
      isDark: () => false,
      palette: () => ({ dots: ['a', 'b', 'c', 'd', 'e'], star: 'f' }),
      reduceMotion: () => reduce,
    });
    stops.push(sphere.stop);
    const first = queue.shift();
    expect(first, 'the first frame is always asked for').toBeDefined();
    first?.(0);
    return { queue, ctx, sphere };
  }

  function resizeBy(pixels: number) {
    Object.defineProperty(window, 'innerWidth', {
      configurable: true,
      value: window.innerWidth + pixels,
    });
    window.dispatchEvent(new Event('resize'));
    vi.advanceTimersByTime(200);
  }

  it('keeps asking for frames normally', () => {
    const { queue, ctx } = start(false);
    expect(ctx.arc).toHaveBeenCalled();
    expect(queue).toHaveLength(1);
  });

  it('draws one frame and asks for no more when less motion is wanted', () => {
    const { queue, ctx } = start(true);
    expect(ctx.arc).toHaveBeenCalled();
    expect(queue).toHaveLength(0);
  });

  it('redraws once after a resize, still without a loop', () => {
    vi.useFakeTimers();
    const { queue, ctx } = start(true);
    const drawn = ctx.arc.mock.calls.length;
    resizeBy(200);
    expect(ctx.arc.mock.calls.length).toBeGreaterThan(drawn);
    expect(queue).toHaveLength(0);
  });

  /** The dots drawn by the redraw after a resize, with or without pointer activity before it. */
  function redrawAfter(reduce: boolean, pointer: boolean): unknown[][] {
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000);
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    const { ctx } = start(reduce);
    if (pointer) {
      window.dispatchEvent(new MouseEvent('pointerdown', { clientX: 10, clientY: 10 }));
      window.dispatchEvent(new MouseEvent('pointermove', { clientX: 900, clientY: 40 }));
    }
    const before = ctx.arc.mock.calls.length;
    resizeBy(200);
    const dots = ctx.arc.mock.calls.slice(before);
    stops.splice(0).forEach((stop) => stop());
    Object.defineProperty(window, 'innerWidth', { configurable: true, value: originalWidth });
    vi.useRealTimers();
    vi.restoreAllMocks();
    vi.unstubAllGlobals();
    return dots;
  }

  it('the pointer does not move the still sphere when less motion is wanted', () => {
    const calm = redrawAfter(true, false);
    const poked = redrawAfter(true, true);
    expect(calm.length).toBeGreaterThan(0);
    expect(poked).toEqual(calm);
  });

  it('a ripple and the working pulse do nothing when less motion is wanted', () => {
    const calm = redrawAfter(true, false);
    vi.useFakeTimers();
    vi.setSystemTime(1_000_000);
    vi.spyOn(Math, 'random').mockReturnValue(0.5);
    const { ctx, sphere } = start(true);
    sphere.ripple();
    sphere.setBusy(true);
    const before = ctx.arc.mock.calls.length;
    resizeBy(200);
    expect(ctx.arc.mock.calls.slice(before)).toEqual(calm);
  });

  it('refresh reads the colours again and repaints the still frame', () => {
    const palette = vi.fn(() => ({ dots: ['a', 'b', 'c', 'd', 'e'], star: 'f' }));
    vi.stubGlobal('requestAnimationFrame', vi.fn());
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    const ctx = fakeContext();
    const canvas = document.createElement('canvas');
    vi.spyOn(canvas, 'getContext').mockReturnValue(ctx as unknown as CanvasRenderingContext2D);
    const sphere = startParticles({
      canvas,
      isDark: () => true,
      palette,
      reduceMotion: () => true,
    });
    stops.push(sphere.stop);
    expect(palette).toHaveBeenCalledTimes(1);
    sphere.refresh();
    expect(palette).toHaveBeenCalledTimes(2);
    expect(ctx.arc).toHaveBeenCalled();
  });

  it('draws the night stars on their own canvas', () => {
    vi.stubGlobal('requestAnimationFrame', vi.fn());
    vi.stubGlobal('cancelAnimationFrame', vi.fn());
    const ctx = fakeContext();
    const starCtx = fakeContext();
    const canvas = document.createElement('canvas');
    const starCanvas = document.createElement('canvas');
    vi.spyOn(canvas, 'getContext').mockReturnValue(ctx as unknown as CanvasRenderingContext2D);
    vi.spyOn(starCanvas, 'getContext').mockReturnValue(
      starCtx as unknown as CanvasRenderingContext2D,
    );
    const sphere = startParticles({
      canvas,
      starCanvas,
      isDark: () => true,
      palette: () => ({ dots: ['a', 'b', 'c', 'd', 'e'], star: 'white' }),
    });
    stops.push(sphere.stop);
    expect(starCtx.arc).toHaveBeenCalledTimes(
      createStars(window.innerWidth, window.innerHeight).length,
    );
    expect(starCtx.fillStyle).toBe('white');
  });
});
