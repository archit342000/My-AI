import { act, render } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { startParticles } from '../../lib/particles';
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
  let stop: ReturnType<typeof vi.fn>;

  beforeEach(() => {
    stop = vi.fn();
    started.mockReset();
    started.mockReturnValue(stop);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    root.className = '';
  });

  it('starts the canvas once and tells it whether less motion is wanted', () => {
    stubReducedMotion(true);
    render(<AmbientBackground />);
    expect(started).toHaveBeenCalledTimes(1);
    expect(started.mock.calls[0]?.[0].reduceMotion?.()).toBe(true);
  });

  it('with less motion, a theme flip stops the still frame and draws a new one', async () => {
    stubReducedMotion(true);
    render(<AmbientBackground />);
    await act(async () => root.classList.add('dark'));
    await flush();
    expect(stop).toHaveBeenCalledTimes(1);
    expect(started).toHaveBeenCalledTimes(2);
  });

  it('with less motion, an unrelated class on <html> does not redraw', async () => {
    stubReducedMotion(true);
    render(<AmbientBackground />);
    await act(async () => root.classList.add('is-ios'));
    await flush();
    expect(started).toHaveBeenCalledTimes(1);
  });

  it('with normal motion, a theme flip leaves the running canvas alone', async () => {
    stubReducedMotion(false);
    render(<AmbientBackground />);
    await act(async () => root.classList.add('dark'));
    await flush();
    expect(started).toHaveBeenCalledTimes(1);
    expect(started.mock.calls[0]?.[0].reduceMotion?.()).toBe(false);
  });

  it('stops the canvas and the observer when it unmounts', async () => {
    stubReducedMotion(true);
    const { unmount } = render(<AmbientBackground />);
    unmount();
    expect(stop).toHaveBeenCalledTimes(1);
    await act(async () => root.classList.add('dark'));
    await flush();
    expect(started).toHaveBeenCalledTimes(1);
  });
});
