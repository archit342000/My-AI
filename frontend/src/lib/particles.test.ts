import { describe, expect, it } from 'vitest';
import { createParticles, particleAlpha, particleCount, particleRadius, rotatePoint } from './particles';

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
