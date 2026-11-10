import { renderHook } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { usePlatformClass } from './usePlatformClass';

const IPHONE =
  'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Safari/604.1';
const DESKTOP = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/120 Safari/537.36';

function touchMove(target: Element) {
  const event = new Event('touchmove', { bubbles: true, cancelable: true });
  target.dispatchEvent(event);
  return event.defaultPrevented;
}

afterEach(() => {
  vi.unstubAllGlobals();
  document.documentElement.classList.remove('is-ios');
  document.body.innerHTML = '';
});

describe('usePlatformClass', () => {
  it('on iOS marks the page, blocks touches on the background and lets scroll areas scroll', () => {
    vi.stubGlobal('navigator', { userAgent: IPHONE, maxTouchPoints: 5 });
    document.body.innerHTML = '<div id="bg">x</div><div id="messages"><i id="in">y</i></div>';
    renderHook(() => usePlatformClass());
    expect(document.documentElement.classList.contains('is-ios')).toBe(true);
    expect(touchMove(document.getElementById('bg') as Element)).toBe(true);
    expect(touchMove(document.getElementById('in') as Element)).toBe(false);
  });

  it('an iPad that reports itself as a Mac is treated as iOS', () => {
    vi.stubGlobal('navigator', {
      userAgent: 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15',
      maxTouchPoints: 5,
    });
    renderHook(() => usePlatformClass());
    expect(document.documentElement.classList.contains('is-ios')).toBe(true);
  });

  it('elsewhere does nothing', () => {
    vi.stubGlobal('navigator', { userAgent: DESKTOP, maxTouchPoints: 0 });
    document.body.innerHTML = '<div id="bg">x</div>';
    renderHook(() => usePlatformClass());
    expect(document.documentElement.classList.contains('is-ios')).toBe(false);
    expect(touchMove(document.getElementById('bg') as Element)).toBe(false);
  });

  it('removes the class and the listener when unmounted', () => {
    vi.stubGlobal('navigator', { userAgent: IPHONE, maxTouchPoints: 5 });
    document.body.innerHTML = '<div id="bg">x</div>';
    renderHook(() => usePlatformClass()).unmount();
    expect(document.documentElement.classList.contains('is-ios')).toBe(false);
    expect(touchMove(document.getElementById('bg') as Element)).toBe(false);
  });
});
