import { afterEach, describe, expect, it, vi } from 'vitest';
import {
  createParticles,
  particleAlpha,
  particleCount,
  particleRadius,
  rotatePoint,
  startParticles,
} from './particles';

describe('particles', () => {
  it('uses fewer particles on touch devices', () => {
    expect(particleCount(true)).toBe(250);
    expect(particleCount(false)).toBe(900);
  });

  it('sizes the sphere per viewport', () => {
    expect(particleRadius(390, 844)).toBeCloseTo(Math.min(390, 844) * 0.38);
    expect(particleRadius(1440, 900)).toBeCloseTo(Math.max(300, 900 * 0.28));
  });

  it('creates the requested number of unit-sphere points with bounded sizes', () => {
    const ps = createParticles(50, 300, () => 0.5);
    expect(ps).toHaveLength(50);
    for (const p of ps) {
      expect(Math.hypot(p.ux, p.uy, p.uz)).toBeCloseTo(1, 5);
      expect(p.size).toBeGreaterThanOrEqual(1.5);
      expect(p.size).toBeLessThanOrEqual(4);
    }
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
    stops.push(startParticles({ canvas, isDark: () => false, reduceMotion: () => reduce }));
    const first = queue.shift();
    expect(first, 'the first frame is always asked for').toBeDefined();
    first?.(0);
    return { queue, ctx };
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
});
