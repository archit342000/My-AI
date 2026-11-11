import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { startParticles } from '../../lib/particles';
import { rippleSphere, setSphereBusy } from '../../lib/sphere-signal';
import { AmbientBackground } from './AmbientBackground';

vi.mock('../../lib/particles', () => ({ startParticles: vi.fn() }));

const started = vi.mocked(startParticles);
const root = document.documentElement;

function stubReducedMotion(reduce: boolean) {
  vi.stubGlobal('matchMedia', (query: string) => ({
    matches: reduce && query.includes('prefers-reduced-motion'),
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  }));
}

/** Lets the MutationObserver deliver its records. */
async function flush() {
  await act(async () => {
    await Promise.resolve();
  });
}

describe('AmbientBackground', () => {
  const sphere = { stop: vi.fn(), ripple: vi.fn(), setBusy: vi.fn(), refresh: vi.fn() };

  beforeEach(() => {
    Object.values(sphere).forEach((fn) => fn.mockReset());
    started.mockReset();
    started.mockReturnValue(sphere);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    setSphereBusy(false);
    root.className = '';
    root.style.cssText = '';
  });

  it('starts the sphere once with a star canvas, the shared dot colours and the motion setting', () => {
    stubReducedMotion(true);
    for (const n of [1, 2, 3, 4, 5]) root.style.setProperty(`--dot-${n}`, `colour-${n}`);
    const { container } = render(<AmbientBackground />);
    expect(started).toHaveBeenCalledTimes(1);
    const options = started.mock.calls[0]?.[0];
    expect(options?.canvas).toBe(container.querySelector('#bg-stars'));
    expect(options?.starCanvas).toBe(container.querySelector('#bg-night'));
    expect(options?.reduceMotion?.()).toBe(true);
    expect(options?.palette().dots).toEqual([
      'colour-1',
      'colour-2',
      'colour-3',
      'colour-4',
      'colour-5',
    ]);
  });

  it('passes ripples and the working pulse on to the sphere', () => {
    stubReducedMotion(false);
    render(<AmbientBackground />);
    rippleSphere(2);
    setSphereBusy(true);
    expect(sphere.ripple).toHaveBeenCalledWith(2);
    expect(sphere.setBusy).toHaveBeenLastCalledWith(true);
  });

  it('reads the colours again when the theme flips, and only then', async () => {
    stubReducedMotion(false);
    render(<AmbientBackground />);
    await act(async () => root.classList.add('is-ios'));
    await flush();
    expect(sphere.refresh).not.toHaveBeenCalled();
    await act(async () => root.classList.add('dark'));
    await flush();
    expect(sphere.refresh).toHaveBeenCalledTimes(1);
    expect(started).toHaveBeenCalledTimes(1);
  });

  it('stops the sphere, the signal and the observer when it unmounts', async () => {
    stubReducedMotion(true);
    const { unmount } = render(<AmbientBackground />);
    unmount();
    expect(sphere.stop).toHaveBeenCalledTimes(1);
    rippleSphere();
    await act(async () => root.classList.add('dark'));
    await flush();
    expect(sphere.ripple).not.toHaveBeenCalled();
    expect(sphere.refresh).not.toHaveBeenCalled();
  });
});
