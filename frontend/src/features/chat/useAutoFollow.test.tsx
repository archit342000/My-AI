import { act, renderHook } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { useAutoFollow } from './useAutoFollow';

function setup() {
  const el = document.createElement('div');
  Object.defineProperty(el, 'scrollHeight', { value: 2000, configurable: true });
  Object.defineProperty(el, 'clientHeight', { value: 600, configurable: true });
  const scrollTo = vi.fn<(options?: ScrollToOptions) => void>();
  el.scrollTo = scrollTo as HTMLElement['scrollTo'];
  const ref = { current: el };
  const view = renderHook(() => useAutoFollow(ref, 'c1', 0));
  (el.scrollTo as unknown as { mockClear(): void }).mockClear(); // the first mount scrolls to the end itself
  return { el, view };
}

describe('useAutoFollow on a viewport resize', () => {
  beforeEach(() => {
    vi.stubGlobal('requestAnimationFrame', (fn: FrameRequestCallback) => {
      fn(0);
      return 0;
    });
  });
  afterEach(() => {
    vi.unstubAllGlobals();
    Reflect.deleteProperty(window, 'visualViewport');
  });

  it('a reader pinned to the bottom is scrolled to the end again when the window resizes', () => {
    const { el } = setup();
    act(() => window.dispatchEvent(new Event('resize')));
    expect(el.scrollTo).toHaveBeenCalledWith({ top: 2000, behavior: 'instant' });
  });

  it('a reader who scrolled up is left where they are', () => {
    const { el } = setup();
    el.scrollTop = 900;
    act(() => el.dispatchEvent(new Event('scroll'))); // moving up from the bottom unpins
    el.scrollTop = 500;
    act(() => el.dispatchEvent(new Event('scroll')));
    (el.scrollTo as unknown as { mockClear(): void }).mockClear();
    act(() => window.dispatchEvent(new Event('resize')));
    expect(el.scrollTo).not.toHaveBeenCalled();
  });

  it('follows the visual viewport too, and stops listening when unmounted', () => {
    const listeners = new Set<() => void>();
    Object.defineProperty(window, 'visualViewport', {
      configurable: true,
      value: {
        addEventListener: (_t: string, fn: () => void) => listeners.add(fn),
        removeEventListener: (_t: string, fn: () => void) => listeners.delete(fn),
      },
    });
    const { el, view } = setup();
    act(() => listeners.forEach((fn) => fn()));
    expect(el.scrollTo).toHaveBeenCalled();
    view.unmount();
    expect(listeners.size).toBe(0);
  });
});
